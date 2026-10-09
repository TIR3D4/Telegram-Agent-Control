import re
import hmac
import hashlib
from datetime import timedelta
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from .config import settings
from .gateway import Identity, grant_identity, require

bearer = HTTPBearer(auto_error=False)
SENSITIVE = re.compile(
    r"token|secret|password|authorization|passport_data|credentials|session_string|api_hash", re.I
)
TOKEN = re.compile(
    r"\b\d{6,12}:[A-Za-z0-9_-]{25,}\b|\btac_[A-Za-z0-9_-]{32,}\b|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
)


def redact(obj):
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if SENSITIVE.search(k) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        obj = TOKEN.sub("[REDACTED]", obj)
        for key in [
            settings().owner_key,
            settings().agent_key,
            settings().reader_key,
            settings().bot_token,
            settings().webhook_secret,
        ]:
            val = key.get_secret_value()
            if val:
                obj = obj.replace(val, "[REDACTED]")
        return obj
    return obj


def secret_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def consume(db, key, limit, expires_at):
    from .db import RateBucket

    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    statement = insert(RateBucket).values(key=key, count=1, expires_at=expires_at)
    count = db.scalar(
        statement.on_conflict_do_update(
            index_elements=["key"], set_={"count": RateBucket.count + 1}
        ).returning(RateBucket.count)
    )
    if count > limit:
        raise HTTPException(429, "Agent quota exceeded", headers={"Retry-After": "60"})


def authenticate(token, *, meter=True):
    from .db import Session, AgentGrant, now

    if len(token) > 16384:
        raise HTTPException(401, "Invalid credential")
    for role, secret in [
        ("owner", settings().owner_key),
        ("agent", settings().agent_key),
        ("reader", settings().reader_key),
    ]:
        if secret.get_secret_value() and hmac.compare_digest(token, secret.get_secret_value()):
            return Identity(
                role,
                "ADMIN" if role == "owner" else "READ" if role == "reader" else "OPERATE",
                human=role == "owner",
            )
    claims = None
    with Session.begin() as db:
        if token.startswith("tac_"):
            grant = db.scalar(select(AgentGrant).where(AgentGrant.secret_hash == secret_hash(token)))
        else:
            from .oauth import verify

            claims = verify(token)
            grant = db.scalar(select(AgentGrant).where(AgentGrant.oauth_subject == claims["sub"]))
        if not grant:
            raise HTTPException(401, "Unknown agent grant")
        who = grant_identity(grant, claims["scope"].split() if claims else None)
        if meter:
            stamp = now()
            consume(
                db,
                f"request:{grant.id}:{int(stamp.timestamp()) // 60}",
                grant.rpm,
                stamp + timedelta(minutes=2),
            )
        return who


def route_scope(path, verb):
    part = path.removeprefix("/v1/").split("/")[0]
    if part in {"agents"}:
        return "human"
    if part in {"capabilities", "methods", "types", "validate", "system", "accounts", "channels"}:
        return "system:read"
    if part in {"operations", "posts"}:
        return "posts:read" if verb == "GET" else None  # Mutation services check exact method/resource.
    if part == "assets":
        return "media:read" if verb == "GET" else "media:write"
    if part in {"workflows", "workflow-runs"}:
        return "workflows:read" if verb == "GET" else "workflows:write"
    if part in {"emojis", "emoji-roles"}:
        return "emoji:read" if verb == "GET" else "emoji:write"
    if part == "logs" or part == "traces":
        return "logs:read"
    if part == "metrics":
        return "metrics:read"
    if part == "database":
        return "database:read"
    if part == "updates":
        return "telegram:read"
    if part == "keyboards":
        return "keyboards:write"
    if part == "settings":
        return "settings:read"
    if part == "admin":
        return "maintenance:request"
    return "human"


def principal(request: Request, auth: HTTPAuthorizationCredentials | None = Depends(bearer)):
    try:
        if not auth:
            raise HTTPException(401, "Valid bearer credential required")
        who = authenticate(auth.credentials)
        request.state.actor = str(who)
        scope = route_scope(request.url.path, request.method)
        if scope == "human" and not who.human:
            raise HTTPException(403, "Human owner required")
        if scope and scope != "human":
            require(who, scope)
        return who
    except HTTPException as e:
        if e.status_code == 401:
            from .oauth import challenge

            e.headers = {"WWW-Authenticate": challenge()}
        raise


def owner(role=Depends(principal)):
    if not role.human:
        raise HTTPException(403, "Independent human owner required; agents cannot approve")
    return role


def writer(role=Depends(principal)):
    if role.preset == "READ" and not role.human:
        raise HTTPException(403, "Read-only grant")
    return role
