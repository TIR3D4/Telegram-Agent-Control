"""Human console sessions. Agent bearer tokens never become owner sessions."""

import hmac
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import delete

from .config import settings
from .db import Session, RuntimeState, now
from .gateway import Identity
from .passwords import verify_password
from .security import consume, secret_hash

router = APIRouter(prefix="/v1/session", tags=["Console login"])
COOKIE = "tac_session"
LIFETIME = 8 * 3600


def same_origin(request):
    origin = request.headers.get("origin")
    expected = settings().public_url.rstrip("/")
    if origin and origin != expected:
        raise HTTPException(403, "Cross-origin login or mutation rejected")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site request rejected")


def session_key(request):
    token = request.cookies.get(COOKIE, "")
    if len(token) != 64:
        raise HTTPException(401, "Sign in to the console")
    return "web-session:" + secret_hash(token)


def read_session(request):
    with Session() as db:
        row = db.get(RuntimeState, session_key(request))
        value = row.value if row else {}
    fingerprint = secret_hash(settings().owner_password_hash.get_secret_value())
    if value.get("expires", 0) <= now().timestamp() or value.get("password_version") != fingerprint:
        raise HTTPException(401, "Session expired; sign in again")
    return value


def session_identity(request):
    value = read_session(request)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        same_origin(request)
        if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), value["csrf"]):
            raise HTTPException(403, "Invalid CSRF token; reload the console")
    return Identity("owner", "ADMIN", human=True)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=1024)


@router.post("")
def login(data: Login, request: Request, response: Response):
    same_origin(request)
    config = settings()
    if not config.owner_password_hash.get_secret_value():
        raise HTTPException(503, "Console login is not configured. Run scripts/tacctl setup once.")
    # A global limit also bounds hashing work and ignores untrusted forwarded IP headers.
    stamp = now()
    with Session.begin() as db:
        consume(db, f"login:global:{int(stamp.timestamp()) // 60}", 30, stamp + timedelta(minutes=2))
    valid = verify_password(data.password, config.owner_password_hash.get_secret_value())
    if not hmac.compare_digest(data.username.encode(), config.owner_username.encode()) or not valid:
        raise HTTPException(401, "Incorrect username or password")
    token = secrets.token_hex(32)
    csrf = secrets.token_urlsafe(32)
    with Session.begin() as db:
        # Bounded session storage, expired sessions are removed on each successful login.
        rows = db.query(RuntimeState).filter(RuntimeState.key.like("web-session:%")).all()
        for row in rows:
            if row.value.get("expires", 0) <= stamp.timestamp():
                db.delete(row)
        db.add(
            RuntimeState(
                key="web-session:" + secret_hash(token),
                value={
                    "csrf": csrf,
                    "expires": stamp.timestamp() + LIFETIME,
                    "password_version": secret_hash(config.owner_password_hash.get_secret_value()),
                },
            )
        )
    response.set_cookie(
        COOKIE,
        token,
        max_age=LIFETIME,
        httponly=True,
        secure=urlsplit(config.public_url).scheme == "https",
        samesite="strict",
        path="/",
    )
    return {"role": "owner", "csrf": csrf}


@router.get("")
def current(request: Request):
    value = read_session(request)
    return {"role": "owner", "csrf": value["csrf"]}


@router.delete("")
def logout(request: Request, response: Response):
    session_identity(request)
    with Session.begin() as db:
        db.execute(delete(RuntimeState).where(RuntimeState.key == session_key(request)))
    response.delete_cookie(COOKIE, path="/")
    return {"signed_out": True}
