from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, String, Text, DateTime, Integer, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, mapped_column, sessionmaker
from .config import settings


def now():
    return datetime.now(timezone.utc)


def uid():
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class Operation(Base):
    __tablename__ = "operations"
    id = mapped_column(String(32), primary_key=True, default=uid)
    key = mapped_column(String(160), unique=True, nullable=False)
    method = mapped_column(String(100), nullable=False)
    payload = mapped_column(JSON, nullable=False)
    attachments = mapped_column(JSON, default=dict, nullable=False)
    digest = mapped_column(String(64), nullable=False)
    status = mapped_column(String(32), default="draft", index=True)
    actor = mapped_column(String(80), nullable=False)
    approved_by = mapped_column(String(80))
    approved_digest = mapped_column(String(64))
    approved_until = mapped_column(DateTime(timezone=True))
    run_at = mapped_column(DateTime(timezone=True), default=now, index=True)
    started_at = mapped_column(DateTime(timezone=True))
    finished_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), default=now, index=True)
    lease_until = mapped_column(DateTime(timezone=True))
    execution_token = mapped_column(String(32))
    trace_id = mapped_column(String(32), index=True)
    attempts = mapped_column(Integer, default=0)
    result = mapped_column(JSON)
    error = mapped_column(JSON)
    workflow_run_id = mapped_column(String(32), index=True)
    step_index = mapped_column(Integer)


class Audit(Base):
    __tablename__ = "audit_events"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    at = mapped_column(DateTime(timezone=True), default=now, index=True)
    actor = mapped_column(String(80), nullable=False)
    action = mapped_column(String(100), index=True)
    resource_id = mapped_column(String(100), index=True)
    details = mapped_column(JSON, default=dict)
    request_id = mapped_column(String(32), index=True)
    trace_id = mapped_column(String(32), index=True)


class Asset(Base):
    __tablename__ = "assets"
    actor = mapped_column(String(80), default="owner", server_default="owner", nullable=False)
    id = mapped_column(String(32), primary_key=True, default=uid)
    name = mapped_column(String(200))
    mime = mapped_column(String(120))
    size = mapped_column(Integer)
    sha256 = mapped_column(String(64), index=True)
    created_at = mapped_column(DateTime(timezone=True), default=now)


class Update(Base):
    __tablename__ = "telegram_updates"
    id = mapped_column(Integer, primary_key=True)
    body = mapped_column(JSON)
    received_at = mapped_column(DateTime(timezone=True), default=now)


class Workflow(Base):
    __tablename__ = "workflows"
    actor = mapped_column(String(80), default="owner", server_default="owner", nullable=False)
    id = mapped_column(String(32), primary_key=True, default=uid)
    name = mapped_column(String(150))
    steps = mapped_column(JSON, nullable=False)
    trigger = mapped_column(JSON, nullable=False)
    digest = mapped_column(String(64))
    approved_digest = mapped_column(String(64))
    approved_until = mapped_column(DateTime(timezone=True))
    active = mapped_column(Boolean, default=False)
    next_run = mapped_column(DateTime(timezone=True), index=True)
    timezone = mapped_column(String(80), default="Asia/Tehran")
    max_runs = mapped_column(Integer, default=1)
    runs_count = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime(timezone=True), default=now)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    actor = mapped_column(String(80), default="owner", server_default="owner", nullable=False)
    __table_args__ = (UniqueConstraint("workflow_id", "occurrence_key"),)
    id = mapped_column(String(32), primary_key=True, default=uid)
    workflow_id = mapped_column(String(32), index=True)
    occurrence_key = mapped_column(String(100))
    steps = mapped_column(JSON)
    status = mapped_column(String(30), default="running")
    cursor = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime(timezone=True), default=now)


class Emoji(Base):
    __tablename__ = "emojis"
    id = mapped_column(String(80), primary_key=True)
    pack = mapped_column(String(150), index=True)
    alt = mapped_column(String(100))
    file_id = mapped_column(Text)
    format = mapped_column(String(10))
    asset_id = mapped_column(String(32))
    preview_id = mapped_column(String(32))
    labels = mapped_column(JSON, default=dict)
    reviewed = mapped_column(Boolean, default=False)
    error = mapped_column(String(250))
    updated_at = mapped_column(DateTime(timezone=True), default=now)


class RoleBinding(Base):
    __tablename__ = "emoji_roles"
    role = mapped_column(String(80), primary_key=True)
    emoji_id = mapped_column(String(80), nullable=False)


class RuntimeState(Base):
    __tablename__ = "runtime_state"
    key = mapped_column(String(100), primary_key=True)
    value = mapped_column(JSON)


class AgentGrant(Base):
    __tablename__ = "agent_grants"
    id = mapped_column(String(32), primary_key=True, default=uid)
    name = mapped_column(String(120), nullable=False)
    preset = mapped_column(String(16), nullable=False)
    secret_hash = mapped_column(String(64), unique=True)
    oauth_subject = mapped_column(String(255), unique=True)
    scopes = mapped_column(JSON, nullable=False)
    chats = mapped_column(JSON, nullable=False)
    methods = mapped_column(JSON, nullable=False)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at = mapped_column(DateTime(timezone=True))
    rpm = mapped_column(Integer, default=120, nullable=False)
    daily_operations = mapped_column(Integer, default=500, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=now)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key = mapped_column(String(160), primary_key=True)
    count = mapped_column(Integer, nullable=False, default=0)
    expires_at = mapped_column(DateTime(timezone=True), index=True)


class AdminRequest(Base):
    __tablename__ = "admin_requests"
    id = mapped_column(String(32), primary_key=True, default=uid)
    actor = mapped_column(String(80), nullable=False)
    action = mapped_column(String(80), nullable=False)
    parameters = mapped_column(JSON, nullable=False)
    digest = mapped_column(String(64), nullable=False)
    status = mapped_column(String(20), default="draft", nullable=False)
    approved_by = mapped_column(String(80))
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=now)
    result = mapped_column(JSON)


def make_engine(url=None):
    url = url or settings().database_url
    if url.startswith("sqlite"):
        settings().storage_dir.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        url, pool_pre_ping=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
    )


engine = make_engine()
Session = sessionmaker(engine, expire_on_commit=False)


def record(db, actor, action, resource_id="", details=None):
    from .security import redact

    from .gateway import request_context

    ctx = request_context.get()
    db.add(
        Audit(
            actor=str(actor),
            action=action,
            resource_id=resource_id,
            details=redact(details or {}),
            request_id=ctx.get("request_id"),
            trace_id=ctx.get("trace_id"),
        )
    )
