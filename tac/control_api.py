"""Typed control-plane operations. All publishing uses the existing operation gateway."""

import base64
import binascii
import secrets
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime
from sqlalchemy import select, func
from .db import Session, AgentGrant, AdminRequest, Operation, Asset, Workflow, Audit, RuntimeState, now
from .security import principal, owner, writer, secret_hash, redact
from .gateway import PRESETS, READ_METHODS, POST_METHODS, require, resource, owned_query, utc
from .registry import registry, validate
from .operations import submit, digest, serialize
from .config import settings
from .db import record

router = APIRouter(prefix="/v1")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GrantInput(Input):
    name: str = Field(min_length=1, max_length=120)
    preset: Literal["READ", "OPERATE", "ADMIN"] = "OPERATE"
    scopes: list[str] | None = None
    chats: list[str] = Field(default_factory=list, max_length=100)
    methods: list[str] | None = None
    expires_at: AwareDatetime
    oauth_subject: str | None = Field(default=None, max_length=255)
    rpm: int = Field(default=120, ge=1, le=1000)
    daily_operations: int = Field(default=500, ge=1, le=10000)


def public_grant(g):
    return {
        "id": g.id,
        "name": g.name,
        "preset": g.preset,
        "scopes": g.scopes,
        "chats": g.chats,
        "methods": g.methods,
        "expires_at": g.expires_at,
        "revoked_at": g.revoked_at,
        "rpm": g.rpm,
        "daily_operations": g.daily_operations,
        "oauth_bound": bool(g.oauth_subject),
    }


@router.get("/agents", tags=["Agent governance"])
def agents(role=Depends(owner)):
    with Session() as db:
        return [
            public_grant(g)
            for g in db.scalars(select(AgentGrant).order_by(AgentGrant.created_at.desc()).limit(200))
        ]


@router.post("/agents", status_code=201, tags=["Agent governance"])
def issue_agent(body: GrantInput, role=Depends(owner)):
    if not now() < body.expires_at <= now() + timedelta(days=365):
        raise ValueError("Credential lifetime must be between now and 365 days")
    scopes = set(body.scopes if body.scopes is not None else PRESETS[body.preset])
    methods = set(
        body.methods
        if body.methods is not None
        else READ_METHODS | (POST_METHODS if body.preset != "READ" else set())
    )
    chats = {c.lower() for c in body.chats}
    if not scopes <= PRESETS[body.preset] or not methods <= set(registry()["methods"]):
        raise ValueError("Scope/method is not supported by the selected preset")
    if body.preset == "READ" and any(registry()["methods"][m]["effect"] != "read" for m in methods):
        raise ValueError("READ cannot grant Telegram writes")
    if not chats <= settings().chats:
        raise ValueError("Agent channels must be a subset of the server allowlist")
    token = None if body.oauth_subject else "tac_" + secrets.token_urlsafe(40)
    with Session.begin() as db:
        grant = AgentGrant(
            name=body.name,
            preset=body.preset,
            scopes=sorted(scopes),
            methods=sorted(methods),
            chats=sorted(chats),
            secret_hash=secret_hash(token) if token else None,
            oauth_subject=body.oauth_subject,
            expires_at=body.expires_at,
            rpm=body.rpm,
            daily_operations=body.daily_operations,
        )
        db.add(grant)
        db.flush()
        record(db, role, "agent.created", grant.id, {"preset": grant.preset, "scopes": grant.scopes})
        return {
            "grant": public_grant(grant),
            "credential": token,
            "note": "Credential is shown once; never place it in a URL or logs.",
        }


class MaintenanceInput(Input):
    action: Literal[
        "rotate_credential", "revoke_credential", "delete_asset", "restore_backup", "pause_execution"
    ]
    parameters: dict


class Consent(Input):
    expected_digest: str


def validate_change(body):
    expected = {
        "rotate_credential": {"agent_id"},
        "revoke_credential": {"agent_id"},
        "delete_asset": {"asset_id"},
        "restore_backup": {"backup_name"},
        "pause_execution": {"enabled"},
    }[body.action]
    if set(body.parameters) != expected:
        raise ValueError("Maintenance parameters must be exactly " + ", ".join(sorted(expected)))
    if body.action == "pause_execution":
        if not isinstance(body.parameters["enabled"], bool):
            raise ValueError("enabled must be boolean")
    elif not all(isinstance(v, str) and 1 <= len(v) <= 100 for v in body.parameters.values()):
        raise ValueError("Resource identifiers must be bounded strings")
    if body.action == "restore_backup":
        import re

        if not re.fullmatch(r"\d{8}T\d{6}Z", body.parameters["backup_name"]):
            raise ValueError("Backup name must be an installation timestamp")


@router.post("/admin/requests", status_code=201, tags=["Maintenance"])
def request_change(body: MaintenanceInput, role=Depends(writer)):
    require(role, "maintenance:request")
    validate_change(body)
    with Session.begin() as db:
        if (
            body.action in {"rotate_credential", "revoke_credential"}
            and not role.human
            and str(role) != "agent:" + body.parameters["agent_id"]
        ):
            raise HTTPException(403, "Agents may request changes only to their own credential")
        if body.action == "delete_asset":
            a = db.get(Asset, body.parameters["asset_id"])
            if not a:
                raise HTTPException(404, "Asset not found")
            resource(role, a)
        request = AdminRequest(
            actor=str(role),
            action=body.action,
            parameters=body.parameters,
            digest=digest(body.action, body.parameters),
            expires_at=now() + timedelta(minutes=15),
        )
        db.add(request)
        db.flush()
        record(db, role, "maintenance.requested", request.id, {"action": request.action})
        return change_view(request)


def change_view(r):
    return {
        "id": r.id,
        "actor": r.actor,
        "action": r.action,
        "parameters": r.parameters,
        "digest": r.digest,
        "status": r.status,
        "expires_at": r.expires_at,
        "approved_by": r.approved_by,
        "result": redact(r.result),
    }


@router.get("/admin/requests", tags=["Maintenance"])
def changes(limit: int = 50, role=Depends(principal)):
    with Session() as db:
        return [
            change_view(r)
            for r in db.scalars(
                owned_query(role, AdminRequest)
                .order_by(AdminRequest.created_at.desc())
                .limit(min(max(limit, 1), 100))
            )
        ]


@router.post("/admin/requests/{id}/approve", tags=["Maintenance"])
def consent(id: str, body: Consent, role=Depends(owner)):
    with Session.begin() as db:
        r = db.get(AdminRequest, id, with_for_update=True)
        if not r:
            raise HTTPException(404, "Request not found")
        if r.status != "draft" or r.digest != body.expected_digest or utc(r.expires_at) <= now():
            raise HTTPException(409, "Request changed, expired or already reviewed")
        r.status = "approved"
        r.approved_by = str(role)
        record(db, role, "maintenance.approved", id, {"digest": r.digest})
        return change_view(r)


def checked_request(db, id):
    r = db.get(AdminRequest, id, with_for_update=True)
    if (
        not r
        or r.status != "approved"
        or not r.approved_by
        or utc(r.expires_at) <= now()
        or r.digest != digest(r.action, r.parameters)
    ):
        raise HTTPException(409, "Valid unconsumed human approval required")
    return r


@router.post("/admin/requests/{id}/execute", tags=["Maintenance"])
def execute_change(id: str, role=Depends(owner)):
    token = None
    with Session.begin() as db:
        r = checked_request(db, id)
        if r.action == "restore_backup":
            return {
                **change_view(r),
                "operator_command": "./scripts/tacctl restore-request " + r.id,
                "note": "Restore is performed by the local operator after backup verification; API never executes shell.",
            }
        if r.action in {"rotate_credential", "revoke_credential"}:
            g = db.get(AgentGrant, r.parameters["agent_id"], with_for_update=True)
            if not g:
                raise HTTPException(404, "Agent not found")
            if r.action == "revoke_credential":
                g.revoked_at = now()
            else:
                if g.oauth_subject or g.revoked_at or utc(g.expires_at) <= now():
                    raise HTTPException(409, "Only active local credentials can be rotated")
                token = "tac_" + secrets.token_urlsafe(40)
                g.secret_hash = secret_hash(token)
        elif r.action == "delete_asset":
            a = db.get(Asset, r.parameters["asset_id"], with_for_update=True)
            if not a:
                raise HTTPException(404, "Asset not found")
            for bindings in db.scalars(select(Operation.attachments)).yield_per(500):
                if a.id in bindings.values():
                    raise HTTPException(409, "Asset is referenced by operation history; retain it")
            for steps in db.scalars(select(Workflow.steps)).yield_per(500):
                if any(a.id in step.get("attachments", {}).values() for step in steps):
                    raise HTTPException(409, "Asset is referenced by a workflow")
            from .db import Emoji

            if db.scalar(
                select(Emoji.id).where((Emoji.asset_id == a.id) | (Emoji.preview_id == a.id)).limit(1)
            ):
                raise HTTPException(409, "Asset is used by the emoji catalog")
            # Removing the row while holding its lock prevents concurrent new bindings.
            db.delete(a)
            # File deletion is post-commit. A failed unlink is an orphan, never a broken reference.
            r.result = {"removed_asset_id": a.id}
        elif r.action == "pause_execution":
            state = db.get(RuntimeState, "paused")
            if not state:
                state = RuntimeState(key="paused")
                db.add(state)
            state.value = r.parameters
        r.status = "executed"
        record(db, role, "maintenance.executed", id, {"action": r.action})
        output = change_view(r)
    if output["action"] == "delete_asset":
        (settings().storage_dir / output["parameters"]["asset_id"]).unlink(missing_ok=True)
    if token:
        output["credential"] = token
    return output


class Duplicate(Input):
    idempotency_key: str = Field(min_length=8, max_length=160)
    run_at: AwareDatetime | None = None


@router.post("/operations/{id}/duplicate", tags=["Posts"])
def duplicate(id: str, body: Duplicate, role=Depends(writer)):
    with Session.begin() as db:
        old = db.get(Operation, id)
        if not old:
            raise HTTPException(404, "Not found")
        resource(role, old)
        return serialize(
            submit(db, old.method, old.payload, old.attachments, body.idempotency_key, role, body.run_at)
        )


@router.post("/operations/{id}/retry", tags=["Operations"])
def retry(id: str, body: Duplicate, role=Depends(writer)):
    with Session.begin() as db:
        old = db.get(Operation, id)
        if not old:
            raise HTTPException(404, "Not found")
        resource(role, old)
        if old.status != "failed" or (old.error or {}).get("code") in {"transport_error", "internal_error"}:
            raise HTTPException(
                409, "Only a confirmed failed operation can be retried; reconcile uncertain outcomes"
            )
        new = submit(db, old.method, old.payload, old.attachments, body.idempotency_key, role, body.run_at)
        record(db, role, "operation.retry_requested", new.id, {"previous_id": old.id})
        return serialize(new)


@router.get("/operations/{id}/preview", tags=["Posts"])
def preview_post(id: str, role=Depends(principal)):
    with Session() as db:
        o = db.get(Operation, id)
        if not o:
            raise HTTPException(404, "Not found")
        resource(role, o)
        return {
            "id": o.id,
            "method": o.method,
            "payload": redact(o.payload),
            "attachments": o.attachments,
            "digest": o.digest,
            "status": o.status,
            "rendering": "structural-preview",
            "untrusted_content": True,
            "note": "Telegram client rendering must be verified in an authorized test channel.",
        }


class EncodedAsset(Input):
    name: str = Field(min_length=1, max_length=200)
    mime: str = Field(max_length=120)
    data_base64: str = Field(max_length=1400000)


@router.post("/assets/encoded", tags=["Media"])
def upload_encoded(body: EncodedAsset, role=Depends(writer)):
    from .media import store

    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Invalid base64 media") from None
    if len(data) > 1024 * 1024:
        raise HTTPException(413, "MCP/JSON upload limit is 1 MiB; use multipart REST for larger files")
    with Session.begin() as db:
        a = store(db, data, body.name, body.mime)
        a.actor = str(role)
        record(db, role, "asset.uploaded", a.id, {"bytes": a.size})
        return {"id": a.id, "name": a.name, "mime": a.mime, "size": a.size, "sha256": a.sha256}


@router.get("/assets/{id}/metadata", tags=["Media"])
def metadata(id: str, role=Depends(principal)):
    with Session() as db:
        a = db.get(Asset, id)
        if not a:
            raise HTTPException(404, "Not found")
        resource(role, a)
        return {
            "id": a.id,
            "name": a.name,
            "mime": a.mime,
            "size": a.size,
            "sha256": a.sha256,
            "mime_source": "client supplied; preview decoder verifies supported images",
            "created_at": a.created_at,
        }


class Button(Input):
    text: str = Field(min_length=1, max_length=100)
    url: str | None = Field(default=None, max_length=2048)
    callback_data: str | None = Field(default=None, max_length=64)
    style: Literal["primary", "success", "danger"] | None = None
    icon_custom_emoji_id: str | None = Field(default=None, max_length=80)


class Keyboard(Input):
    rows: list[list[Button]] = Field(max_length=8)


@router.post("/keyboards/build", tags=["Inline keyboards"])
def keyboard(body: Keyboard, role=Depends(writer)):
    import urllib.parse

    if any(not row or len(row) > 8 for row in body.rows):
        raise ValueError("Use 1–8 buttons per row")
    for row in body.rows:
        for b in row:
            if b.url:
                parsed = urllib.parse.urlsplit(b.url)
                if parsed.scheme not in {"https", "http", "tg"} or not (parsed.netloc or parsed.path):
                    raise ValueError("Button URL must use an official HTTP(S) or tg scheme")
    markup = {"inline_keyboard": [[b.model_dump(exclude_none=True) for b in row] for row in body.rows]}
    validate("sendMessage", {"chat_id": "@preview", "text": "preview", "reply_markup": markup})
    return {
        "reply_markup": markup,
        "preview": [[b.text for b in row] for row in body.rows],
        "note": "Callback handlers require an enabled webhook consumer; custom emoji eligibility is enforced by Telegram.",
    }


@router.get("/accounts", tags=["Telegram inspection"])
def accounts(role=Depends(principal)):
    return {
        "items": [
            {
                "id": "default",
                "adapter": "bot-api",
                "configured": bool(settings().bot_token.get_secret_value()),
            }
        ],
        "multi_account": False,
        "mtproto": False,
    }


@router.get("/channels", tags=["Telegram inspection"])
def channels(role=Depends(principal)):
    return {
        "items": [
            {"chat_id": chat, "permission_status": "unverified-use-getChatMember"}
            for chat in sorted(settings().chats if role.human else settings().chats & role.chats)
        ]
    }


@router.get("/metrics", tags=["Diagnostics"])
def metrics(role=Depends(principal)):
    with Session() as db:
        q = select(Operation.status, func.count()).group_by(Operation.status)
        if not role.human:
            q = q.where(Operation.actor == str(role))
        oldest = (
            owned_query(role, Operation)
            .where(Operation.status == "queued")
            .order_by(Operation.run_at)
            .limit(1)
        )
        pending = db.scalar(oldest)
        heartbeat = db.get(RuntimeState, "worker")
        from datetime import datetime

        age = (
            (now() - utc(datetime.fromisoformat(heartbeat.value["heartbeat"]))).total_seconds()
            if heartbeat
            else None
        )
        return {
            "operations": dict(db.execute(q).all()),
            "oldest_due_age_seconds": max(0, (now() - utc(pending.run_at)).total_seconds()) if pending else 0,
            "worker_heartbeat_age_seconds": age,
            "worker_healthy": age is not None and age < settings().worker_stale_seconds,
            "delivery_semantics": "confirmed / uncertain; never exactly-once",
        }


@router.get("/traces/{id}", tags=["Diagnostics"])
def trace_events(id: str, role=Depends(principal)):
    with Session() as db:
        q = select(Audit).where(Audit.trace_id == id)
        if not role.human:
            q = q.where(
                (Audit.actor == str(role))
                | Audit.resource_id.in_(select(Operation.id).where(Operation.actor == str(role)))
            )
        return [
            {
                "id": a.id,
                "at": a.at,
                "action": a.action,
                "request_id": a.request_id,
                "trace_id": a.trace_id,
                "details": redact(a.details),
            }
            for a in db.scalars(q.limit(100))
        ]


@router.get("/settings", tags=["Diagnostics"])
def safe_settings(role=Depends(principal)):
    return {
        "account": "default",
        "timezone": settings().timezone,
        "upload_limit_mb": settings().upload_limit_mb,
        "approval_max_days": settings().approval_max_days,
        "oauth_configured": bool(settings().oauth_issuer),
        "retention_days": settings().retention_days,
        "max_retries": settings().max_retries,
        "configuration_updates": "operator-managed environment; no arbitrary remote config or secret edits",
    }


@router.get("/database/status", tags=["Diagnostics"])
def database_status(role=Depends(principal)):
    from alembic.runtime.migration import MigrationContext
    from importlib.metadata import version

    with Session() as db:
        revision = MigrationContext.configure(db.connection()).get_current_revision()
        backup = db.get(RuntimeState, "backup")
        return {
            "dialect": db.bind.dialect.name,
            "migration_revision": revision,
            "last_verified_backup": backup.value if backup else None,
            "dependencies": {
                name: version(name) for name in ["sqlalchemy", "alembic", "mcp", "httpx", "fastapi"]
            },
            "arbitrary_sql": False,
        }


@router.get("/channels/{chat_id}/analytics", tags=["Telegram inspection"])
def channel_analytics(chat_id: str, role=Depends(principal)):
    from .gateway import authorize_method

    authorize_method(role, "getChat", {"chat_id": chat_id})
    counts = {}
    with Session() as db:
        matches = 0
        sample = db.scalars(
            owned_query(role, Operation).order_by(Operation.created_at.desc()).limit(1000)
        ).all()
        for operation in sample:
            if str(operation.payload.get("chat_id", "")).lower() == chat_id.lower():
                counts[operation.status] = counts.get(operation.status, 0) + 1
                matches += 1
        return {
            "chat_id": chat_id,
            "source": "authorized local operation history",
            "sampled_operations": len(sample),
            "matched": matches,
            "counts": counts,
            "truncated": len(sample) == 1000,
            "telegram_reach_or_views": "not available from general Bot API history",
        }


class SettingsValidation(Input):
    timezone: str
    upload_limit_mb: int = Field(ge=1, le=2000)
    retention_days: int = Field(ge=1, le=3650)


@router.post("/settings/validate", tags=["Diagnostics"])
def validate_settings(body: SettingsValidation, role=Depends(principal)):
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Unknown IANA timezone") from None
    return {
        "valid": True,
        "effective": False,
        "configuration": body.model_dump(),
        "apply": "Human operator must update environment configuration and restart; this endpoint does not mutate secrets or policy.",
    }
