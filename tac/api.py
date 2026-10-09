import hmac
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict, AwareDatetime
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from . import __version__
from .config import settings
from .db import (
    Session,
    Operation,
    Audit,
    Asset,
    Workflow,
    WorkflowRun,
    Emoji,
    RoleBinding,
    Update,
    RuntimeState,
    record,
    now,
)
from .security import principal, owner, writer, redact
from .registry import registry, describe, validate
from .operations import submit, approve, edit, serialize, digest
from .workflows import validate_steps, next_time, on_update
from .media import preview, store


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Call(Input):
    method: str
    payload: dict[str, Any] = Field(default_factory=dict)
    attachments: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=160)
    run_at: AwareDatetime | None = None


class Revision(Input):
    payload: dict[str, Any]
    attachments: dict[str, str] = Field(default_factory=dict)
    expected_digest: str
    run_at: AwareDatetime | None = None


class Approval(Input):
    expected_digest: str


class Validation(Input):
    method: str
    payload: dict[str, Any]


class WorkflowInput(Input):
    name: str = Field(min_length=1, max_length=150)
    steps: list[dict]
    trigger: dict
    timezone: str = "Asia/Tehran"
    max_runs: int = Field(default=1, ge=1, le=10000)


class Label(Input):
    description: str = Field(max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    style: str = ""
    reviewed: bool = False


class Binding(Input):
    emoji_id: str


class Resolution(Input):
    status: str
    result: Any = None
    note: str = Field(min_length=3, max_length=1000)


@asynccontextmanager
async def lifespan(app):
    settings().check()
    from .logging_setup import setup

    setup()
    from .remote_mcp import make_app
    from .mcp_server import mcp

    # A fresh transport per lifespan supports clean restarts and test isolation.
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != "/mcp"]
    app.mount("/mcp", make_app(), name="mcp")
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Telegram Agent Control",
    version=__version__,
    description="Versioned Bot API gateway, durable operations, schedules, workflows, audit and visual emoji catalog.",
    lifespan=lifespan,
)


@app.middleware("http")
async def trace(request, call_next):
    started = time.monotonic()
    rid = uuid4().hex
    try:
        response = await call_next(request)
    except Exception as error:
        details = {"request_id": rid, "error_type": type(error).__name__, "path": request.url.path}
        logging.getLogger("tac.http").error("request_failed", extra=details)
        try:
            with Session.begin() as db:
                record(db, "server", "request.failed", rid, details)
        except Exception:
            # A database outage must not reveal an internal exception or credentials.
            pass
        response = JSONResponse(
            status_code=500, content={"detail": "Internal server error", "request_id": rid}
        )
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    logging.getLogger("tac.http").info(
        "request",
        extra={
            "request_id": rid,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    return response


@app.exception_handler(ValueError)
async def invalid(request, e):
    return JSONResponse(status_code=422, content={"detail": redact(str(e))})


@app.exception_handler(IntegrityError)
async def conflict(request, e):
    return JSONResponse(
        status_code=409,
        content={"detail": "Concurrent or duplicate request; retry with the same idempotency key"},
    )


def get(db, cls, id):
    obj = db.get(cls, id)
    if not obj:
        raise HTTPException(404, "Not found")
    return obj


def row(obj):
    return redact({c.name: getattr(obj, c.name) for c in obj.__table__.columns})


@app.get("/health/live", tags=["Health"])
def live():
    return {"status": "ok", "version": __version__}


@app.get("/health/ready", tags=["Health"])
def ready():
    try:
        with Session() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable") from None
    return {"status": "ready"}


@app.get("/v1/system", tags=["Diagnostics"])
def system(role=Depends(principal)):
    with Session() as db:
        counts = dict(db.execute(select(Operation.status, func.count()).group_by(Operation.status)).all())
        heartbeat = db.get(RuntimeState, "worker")
        paused = db.get(RuntimeState, "paused")
        return {
            "version": __version__,
            "role": role,
            "bot_configured": bool(settings().bot_token.get_secret_value()),
            "allowed_chats": sorted(settings().chats),
            "api_version": registry()["version"],
            "methods": len(registry()["methods"]),
            "types": len(registry()["types"]),
            "operations": counts,
            "worker": heartbeat.value if heartbeat else None,
            "paused": paused.value if paused else {"enabled": False},
            "storage_assets": db.scalar(select(func.count()).select_from(Asset)),
        }


@app.post("/v1/system/pause", tags=["Diagnostics"])
def pause(enabled: bool, role=Depends(owner)):
    with Session.begin() as db:
        state = db.get(RuntimeState, "paused")
        if not state:
            state = RuntimeState(key="paused")
            db.add(state)
        state.value = {"enabled": enabled}
        record(db, role, "system.pause", details=state.value)
    return {"paused": enabled}


@app.get("/v1/capabilities", tags=["Bot API"])
def capabilities(q: str = "", role=Depends(principal)):
    data = registry()
    return {
        "version": data["version"],
        "methods": [
            {"name": n, "effect": e["effect"], "description": e["description"][:200]}
            for n, e in data["methods"].items()
            if q.lower() in (n + " " + e["description"]).lower()
        ],
    }


@app.get("/v1/methods/{name}", tags=["Bot API"])
def method(name: str, role=Depends(principal)):
    return describe(name)


@app.get("/v1/types/{name}", tags=["Bot API"])
def api_type(name: str, role=Depends(principal)):
    if name not in registry()["types"]:
        raise HTTPException(404, "Unknown type")
    return registry()["types"][name]


@app.post("/v1/validate", tags=["Bot API"])
def validation(body: Validation, role=Depends(principal)):
    validate(body.method, body.payload)
    return {
        "valid": True,
        "notes": "Schema and selected cross-field rules checked; Telegram enforces destination, permissions and remaining semantic constraints.",
    }


@app.post("/v1/operations", status_code=201, tags=["Operations"])
def create(body: Call, role=Depends(writer)):
    with Session.begin() as db:
        op = submit(db, body.method, body.payload, body.attachments, body.idempotency_key, role, body.run_at)
        return serialize(op)


@app.get("/v1/operations", tags=["Operations"])
def operations(
    status: str | None = None, limit: int = 50, before: datetime | None = None, role=Depends(principal)
):
    with Session() as db:
        query = select(Operation)
        if status:
            query = query.where(Operation.status == status)
        if before:
            query = query.where(Operation.created_at < before)
        return [
            serialize(o)
            for o in db.scalars(query.order_by(Operation.created_at.desc()).limit(min(max(1, limit), 200)))
        ]


@app.get("/v1/operations/{id}", tags=["Operations"])
def operation(id: str, role=Depends(principal)):
    with Session() as db:
        return serialize(get(db, Operation, id))


@app.patch("/v1/operations/{id}", tags=["Operations"])
def revise(id: str, body: Revision, role=Depends(writer)):
    with Session.begin() as db:
        op = db.scalar(select(Operation).where(Operation.id == id).with_for_update())
        if not op:
            raise HTTPException(404, "Not found")
        edit(db, op, body, role)
        return serialize(op)


@app.post("/v1/operations/{id}/approve", tags=["Operations"])
def approve_operation(id: str, body: Approval, role=Depends(owner)):
    with Session.begin() as db:
        op = db.scalar(select(Operation).where(Operation.id == id).with_for_update())
        if not op:
            raise HTTPException(404, "Not found")
        approve(db, op, role, body.expected_digest)
        return serialize(op)


@app.post("/v1/operations/{id}/cancel", tags=["Operations"])
def cancel(id: str, role=Depends(writer)):
    with Session.begin() as db:
        op = db.scalar(select(Operation).where(Operation.id == id).with_for_update())
        if not op:
            raise HTTPException(404, "Not found")
        if op.status not in ("draft", "queued"):
            raise HTTPException(409, "Already started or terminal")
        op.status = "cancelled"
        record(db, role, "operation.cancelled", id)
        return serialize(op)


@app.post("/v1/operations/{id}/resolve", tags=["Operations"])
def resolve_unknown(id: str, body: Resolution, role=Depends(owner)):
    with Session.begin() as db:
        op = db.get(Operation, id, with_for_update=True)
        if not op:
            raise HTTPException(404, "Not found")
        if op.status != "uncertain" or body.status not in ("succeeded", "failed"):
            raise HTTPException(409, "Only uncertain operations can be reconciled")
        op.status = body.status
        op.result = redact(body.result)
        op.finished_at = now()
        record(db, role, "operation.reconciled", id, {"note": body.note, "status": body.status})
        return serialize(op)


@app.get("/v1/logs", tags=["Diagnostics"])
def logs(
    after: int = 0,
    limit: int = 100,
    resource_id: str | None = None,
    action: str | None = None,
    role=Depends(principal),
):
    with Session() as db:
        query = select(Audit).where(Audit.id > after)
        if resource_id:
            query = query.where(Audit.resource_id == resource_id)
        if action:
            query = query.where(Audit.action == action)
        return [row(a) for a in db.scalars(query.order_by(Audit.id).limit(min(max(limit, 1), 500)))]


@app.get("/v1/database/overview", tags=["Diagnostics"])
def database_overview(role=Depends(principal)):
    from .db import Base

    with Session() as db:
        return {
            "tables": [
                {
                    "name": t.name,
                    "rows": db.scalar(select(func.count()).select_from(t)),
                    "columns": [{"name": c.name, "type": str(c.type)} for c in t.columns],
                }
                for t in Base.metadata.sorted_tables
            ]
        }


@app.post("/v1/assets", tags=["Media"])
async def upload(file: UploadFile = File(...), role=Depends(writer)):
    data = await file.read(settings().upload_limit_mb * 1024 * 1024 + 1)
    with Session.begin() as db:
        asset = store(db, data, file.filename or "upload", file.content_type or "application/octet-stream")
        record(db, role, "asset.uploaded", asset.id, {"bytes": asset.size})
        return row(asset)


@app.get("/v1/assets/{id}", tags=["Media"])
def asset(id: str, role=Depends(principal)):
    with Session() as db:
        a = get(db, Asset, id)
        return FileResponse(
            settings().storage_dir / a.id,
            filename=a.name,
            media_type=a.mime,
            content_disposition_type="attachment",
        )


@app.post("/v1/workflows", status_code=201, tags=["Automation"])
def create_workflow(body: WorkflowInput, role=Depends(writer)):
    validate_steps(body.steps)
    if body.trigger.get("type") == "update" and (
        not body.trigger.get("event") or not body.trigger.get("chat_id")
    ):
        raise ValueError("Update trigger needs event and chat_id")
    due = next_time(body.trigger, body.timezone)
    with Session.begin() as db:
        for step in body.steps:
            if any(not db.get(Asset, a) for a in step.get("attachments", {}).values()):
                raise ValueError("Unknown workflow asset")
        w = Workflow(**body.model_dump(), next_run=due, digest=digest(body.model_dump()))
        db.add(w)
        db.flush()
        record(db, role, "workflow.created", w.id)
        return row(w)


@app.get("/v1/workflows", tags=["Automation"])
def workflows(role=Depends(principal)):
    with Session() as db:
        return [row(w) for w in db.scalars(select(Workflow).order_by(Workflow.created_at.desc()).limit(200))]


@app.post("/v1/workflows/{id}/approve", tags=["Automation"])
def approve_workflow(id: str, body: Approval, role=Depends(owner)):
    with Session.begin() as db:
        w = get(db, Workflow, id)
        if w.digest != body.expected_digest:
            raise HTTPException(409, "Stale workflow")
        w.approved_digest = w.digest
        w.active = True
        record(db, role, "workflow.approved", id, {"digest": w.digest})
        return row(w)


@app.post("/v1/workflows/{id}/pause", tags=["Automation"])
def pause_workflow(id: str, role=Depends(writer)):
    with Session.begin() as db:
        w = db.scalar(select(Workflow).where(Workflow.id == id).with_for_update())
        if not w:
            raise HTTPException(404, "Not found")
        w.active = False
        for r in db.scalars(
            select(WorkflowRun)
            .where(WorkflowRun.workflow_id == id, WorkflowRun.status == "running")
            .with_for_update()
        ):
            r.status = "paused"
            for o in db.scalars(
                select(Operation).where(Operation.workflow_run_id == r.id, Operation.status == "queued")
            ):
                o.status = "cancelled"
        record(db, role, "workflow.paused", id)
        return row(w)


@app.get("/v1/workflow-runs", tags=["Automation"])
def workflow_runs(workflow_id: str | None = None, role=Depends(principal)):
    with Session() as db:
        q = select(WorkflowRun)
        if workflow_id:
            q = q.where(WorkflowRun.workflow_id == workflow_id)
        return [row(r) for r in db.scalars(q.order_by(WorkflowRun.created_at.desc()).limit(200))]


@app.post("/v1/webhook", tags=["Telegram updates"])
async def webhook(request: Request):
    secret = settings().webhook_secret.get_secret_value()
    if not secret or not hmac.compare_digest(
        request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), secret
    ):
        raise HTTPException(401, "Invalid webhook secret")
    raw = await request.body()
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(413, "Update too large")
    body = json.loads(raw)
    if not isinstance(body.get("update_id"), int):
        raise ValueError("Missing update_id")
    try:
        with Session.begin() as db:
            if db.get(Update, body["update_id"]):
                return {"ok": True, "duplicate": True}
            db.add(Update(id=body["update_id"], body=redact(body)))
            db.flush()
            on_update(db, body)
    except IntegrityError:
        return {"ok": True, "duplicate": True}
    return {"ok": True}


@app.get("/v1/updates", tags=["Telegram updates"])
def updates(after: int = -1, role=Depends(principal)):
    with Session() as db:
        return [
            row(u) for u in db.scalars(select(Update).where(Update.id > after).order_by(Update.id).limit(100))
        ]


@app.get("/v1/emojis", tags=["Emoji catalog"])
def emojis(q: str = "", pack: str = "", limit: int = 100, offset: int = 0, role=Depends(principal)):
    with Session() as db:
        query = select(Emoji)
        if pack:
            query = query.where(Emoji.pack == pack)
        if q:
            query = query.where(
                (Emoji.alt.contains(q))
                | (Emoji.id == q)
                | (Emoji.labels.cast(__import__("sqlalchemy").Text).contains(q))
            )
        return [
            row(e)
            for e in db.scalars(
                query.order_by(Emoji.pack, Emoji.id).offset(max(offset, 0)).limit(min(max(limit, 1), 200))
            )
        ]


@app.post("/v1/emojis/{id}/preview", tags=["Emoji catalog"])
def emoji_preview(id: str, role=Depends(writer)):
    with Session.begin() as db:
        return row(preview(db, get(db, Emoji, id)))


@app.patch("/v1/emojis/{id}", tags=["Emoji catalog"])
def label(id: str, body: Label, role=Depends(writer)):
    with Session.begin() as db:
        e = get(db, Emoji, id)
        if body.reviewed and not e.preview_id:
            raise ValueError("Generate and inspect a preview before marking reviewed")
        e.labels = body.model_dump(exclude={"reviewed"})
        e.reviewed = body.reviewed
        record(db, role, "emoji.labeled", id)
        return row(e)


@app.put("/v1/emoji-roles/{name}", tags=["Emoji catalog"])
def bind(name: str, body: Binding, role=Depends(writer)):
    with Session.begin() as db:
        e = get(db, Emoji, body.emoji_id)
        if not e.reviewed:
            raise ValueError("Only reviewed emoji may be bound to roles")
        b = db.get(RoleBinding, name)
        if not b:
            b = RoleBinding(role=name)
            db.add(b)
        b.emoji_id = e.id
        record(db, role, "emoji.bound", e.id, {"role": name})
        return row(b)


@app.get("/v1/emoji-roles", tags=["Emoji catalog"])
def bindings(role=Depends(principal)):
    with Session() as db:
        return [row(b) for b in db.scalars(select(RoleBinding))]


@app.get("/", include_in_schema=False)
def console():
    return FileResponse(Path(__file__).parent / "static/index.html")


app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


class WorkflowRevision(WorkflowInput):
    expected_digest: str


@app.put("/v1/workflows/{id}", tags=["Automation"])
def revise_workflow(id: str, body: WorkflowRevision, role=Depends(writer)):
    validate_steps(body.steps)
    due = next_time(body.trigger, body.timezone)
    with Session.begin() as db:
        w = db.scalar(select(Workflow).where(Workflow.id == id).with_for_update())
        if not w:
            raise HTTPException(404, "Not found")
        if w.digest != body.expected_digest:
            raise HTTPException(409, "Stale workflow revision")
        if w.active or db.scalar(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.workflow_id == id, WorkflowRun.status == "running")
        ):
            raise HTTPException(409, "Pause the workflow before editing")
        for step in body.steps:
            if any(not db.get(Asset, a) for a in step.get("attachments", {}).values()):
                raise ValueError("Unknown asset")
        data = body.model_dump(exclude={"expected_digest"})
        for field, value in data.items():
            setattr(w, field, value)
        w.digest = digest(data)
        w.approved_digest = None
        w.next_run = due
        w.runs_count = 0
        record(db, role, "workflow.revised", id, {"digest": w.digest})
        return row(w)


@app.post("/v1/workflow-runs/{id}/resume", tags=["Automation"])
def resume_run(id: str, role=Depends(owner)):
    with Session.begin() as db:
        r = get(db, WorkflowRun, id)
        w = get(db, Workflow, r.workflow_id)
        if r.status != "paused":
            raise HTTPException(409, "Only paused runs can be resumed")
        if w.approved_digest != w.digest or r.steps != w.steps:
            raise HTTPException(409, "Workflow changed; create a new run")
        ops = db.scalars(select(Operation).where(Operation.workflow_run_id == id).with_for_update()).all()
        for op in ops:
            if op.status == "cancelled":
                op.status = "queued"
                op.approved_digest = op.digest
                op.approved_by = role
        r.status = "running"
        record(db, role, "workflow.resumed", id)
        return row(r)


@app.get("/v1/assets", tags=["Media"])
def list_assets(limit: int = 100, role=Depends(principal)):
    with Session() as db:
        return [
            row(a)
            for a in db.scalars(
                select(Asset).order_by(Asset.created_at.desc()).limit(min(max(limit, 1), 200))
            )
        ]
