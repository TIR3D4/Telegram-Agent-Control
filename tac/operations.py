import hashlib
import json
import re
from datetime import timezone, timedelta
from sqlalchemy import select
from fastapi import HTTPException
from .config import settings
from .db import Operation, Asset, record, now
from .registry import validate, attachment_names, registry
from .gateway import authorize_method, resource, identity, request_context


def digest(*parts):
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def utc(t):
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def check_target(payload):
    if "chat_id" in payload and str(payload["chat_id"]).lower() not in settings().chats:
        raise ValueError("Target chat is not in TAC_ALLOWED_CHATS")


def fingerprint(method, payload, attachments, run_at):
    return digest(method, payload, attachments, utc(run_at).isoformat())


def submit(db, method, payload, attachments, key, actor, run_at=None):
    if not re.fullmatch(r"[A-Za-z0-9_.:\-]{8,160}", key):
        raise ValueError("Idempotency key must be 8–160 safe characters")
    spec = validate(method, payload)
    check_target(payload)
    authorize_method(actor, method, payload)
    if attachment_names(payload) != set(attachments):
        raise ValueError("Every attach:// reference needs exactly one asset binding")
    for asset in attachments.values():
        stored = db.get(Asset, asset, with_for_update=True)
        if not stored:
            raise ValueError("Unknown asset")
        resource(actor, stored)
    old = db.scalar(select(Operation).where(Operation.key == key))
    if old:
        resource(actor, old)
        target_time = run_at or old.run_at
        if old.digest != fingerprint(method, payload, attachments, target_time):
            raise HTTPException(409, "Idempotency key reused with different content")
        return old
    if str(actor).startswith("agent:"):
        from .db import AgentGrant
        from .security import consume

        grant = db.get(AgentGrant, str(actor)[6:])
        day = now().date().isoformat()
        consume(db, f"operation:{grant.id}:{day}", grant.daily_operations, now() + timedelta(days=2))
    run_at = utc(run_at) if run_at else now()
    op = Operation(
        key=key,
        method=method,
        payload=payload,
        attachments=attachments,
        actor=actor,
        trace_id=request_context.get().get("trace_id"),
        run_at=run_at,
        digest=fingerprint(method, payload, attachments, run_at),
        status="queued" if spec["effect"] == "read" else "draft",
    )
    db.add(op)
    db.flush()
    record(db, actor, "operation.created", op.id, {"method": method, "status": op.status})
    return op


def approve(db, op, actor, expected, expires_at=None):
    if not identity(actor).human:
        raise HTTPException(403, "Independent human owner required")
    if op.digest != expected:
        raise HTTPException(409, "Content changed; review current digest")
    if op.status != "draft":
        raise HTTPException(409, "Only drafts can be approved")
    op.approved_until = approval_deadline(op.run_at, expires_at)
    op.approved_by = actor
    op.approved_digest = op.digest
    op.status = "queued"
    record(db, actor, "operation.approved", op.id, {"digest": op.digest})


def edit(db, op, body, actor):
    resource(actor, op)
    authorize_method(actor, op.method, body.payload)
    if op.status not in ("draft", "queued"):
        raise HTTPException(409, "Operation already started; create an edit method operation")
    if op.workflow_run_id:
        raise HTTPException(409, "Manage workflow runs using pause; child content is immutable")
    if body.expected_digest != op.digest:
        raise HTTPException(409, "Stale draft revision")
    validate(op.method, body.payload)
    check_target(body.payload)
    if attachment_names(body.payload) != set(body.attachments):
        raise ValueError("Attachment bindings do not match")
    for aid in body.attachments.values():
        stored = db.get(Asset, aid, with_for_update=True)
        if not stored:
            raise ValueError("Unknown asset")
        resource(actor, stored)
    record(db, actor, "operation.revised", op.id, {"previous_digest": op.digest})
    op.payload = body.payload
    op.attachments = body.attachments
    if body.run_at:
        op.run_at = utc(body.run_at)
    op.digest = fingerprint(op.method, op.payload, op.attachments, op.run_at)
    op.approved_digest = None
    op.approved_until = None
    op.approved_by = None
    op.status = "queued" if registry()["methods"][op.method]["effect"] == "read" else "draft"


def serialize(op):
    from .security import redact

    value = {c.name: getattr(op, c.name) for c in op.__table__.columns}
    result = op.result
    results = result if isinstance(result, list) else [result]
    links = []
    for m in results:
        if isinstance(m, dict) and m.get("message_id") and isinstance(m.get("chat"), dict):
            chat = m["chat"]
            if chat.get("username"):
                links.append(f"https://t.me/{chat['username']}/{m['message_id']}")
            elif str(chat.get("id", "")).startswith("-100"):
                links.append(f"https://t.me/c/{str(chat['id'])[4:]}/{m['message_id']}")
    value["message_links"] = links
    return redact(value)


def approval_deadline(run_at, requested=None):
    deadline = (
        utc(requested)
        if requested
        else max(utc(run_at), now()) + timedelta(seconds=settings().approval_ttl_seconds)
    )
    if (
        deadline <= now()
        or deadline < utc(run_at)
        or deadline > now() + timedelta(days=settings().approval_max_days)
    ):
        raise ValueError(
            "Approval expiry must cover the schedule and be within the configured maximum horizon"
        )
    return deadline
