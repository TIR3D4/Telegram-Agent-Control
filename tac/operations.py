import hashlib
import json
import re
from datetime import timezone
from sqlalchemy import select
from fastapi import HTTPException
from .config import settings
from .db import Operation, Asset, record, now
from .registry import validate, attachment_names, registry


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
    if attachment_names(payload) != set(attachments):
        raise ValueError("Every attach:// reference needs exactly one asset binding")
    for asset in attachments.values():
        if not db.get(Asset, asset):
            raise ValueError("Unknown asset")
    old = db.scalar(select(Operation).where(Operation.key == key))
    if old:
        target_time = run_at or old.run_at
        if old.digest != fingerprint(method, payload, attachments, target_time):
            raise HTTPException(409, "Idempotency key reused with different content")
        return old
    run_at = utc(run_at) if run_at else now()
    op = Operation(
        key=key,
        method=method,
        payload=payload,
        attachments=attachments,
        actor=actor,
        run_at=run_at,
        digest=fingerprint(method, payload, attachments, run_at),
        status="queued" if spec["effect"] == "read" else "draft",
    )
    db.add(op)
    db.flush()
    record(db, actor, "operation.created", op.id, {"method": method, "status": op.status})
    return op


def approve(db, op, actor, expected):
    if op.digest != expected:
        raise HTTPException(409, "Content changed; review current digest")
    if op.status != "draft":
        raise HTTPException(409, "Only drafts can be approved")
    op.approved_by = actor
    op.approved_digest = op.digest
    op.status = "queued"
    record(db, actor, "operation.approved", op.id, {"digest": op.digest})


def edit(db, op, body, actor):
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
    if any(not db.get(Asset, a) for a in body.attachments.values()):
        raise ValueError("Unknown asset")
    record(db, actor, "operation.revised", op.id, {"previous_digest": op.digest})
    op.payload = body.payload
    op.attachments = body.attachments
    if body.run_at:
        op.run_at = utc(body.run_at)
    op.digest = fingerprint(op.method, op.payload, op.attachments, op.run_at)
    op.approved_digest = None
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
