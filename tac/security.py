import re
import hmac
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings

bearer = HTTPBearer(auto_error=False)
SENSITIVE = re.compile(r"token|secret|password|authorization|passport_data|credentials", re.I)
TOKEN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{25,}\b")


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


def principal(auth: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if auth:
        for role, secret in [
            ("owner", settings().owner_key),
            ("agent", settings().agent_key),
            ("reader", settings().reader_key),
        ]:
            if secret.get_secret_value() and hmac.compare_digest(auth.credentials, secret.get_secret_value()):
                return role
    raise HTTPException(401, "Valid bearer key required", headers={"WWW-Authenticate": "Bearer"})


def owner(role=Depends(principal)):
    if role != "owner":
        raise HTTPException(403, "Owner authorization required")
    return role


def writer(role=Depends(principal)):
    if role == "reader":
        raise HTTPException(403, "Read-only key")
    return role
