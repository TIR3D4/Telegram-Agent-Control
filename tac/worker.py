import time
import logging
from datetime import timedelta
import httpx
from sqlalchemy import select
from .db import Session, Operation, RuntimeState, now, record, uid
from .registry import registry
from .operations import check_target
from .telegram import Telegram, TelegramError
from .config import settings
from .security import redact
from .workflows import tick

log = logging.getLogger("tac.worker")


def cycle(client=None):
    api = client or Telegram()
    with Session.begin() as db:
        heartbeat = {"heartbeat": now().isoformat()}
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            statement = insert(RuntimeState).values(key="worker", value=heartbeat)
            db.execute(statement.on_conflict_do_update(index_elements=["key"], set_={"value": heartbeat}))
        else:
            state = db.get(RuntimeState, "worker")
            if not state:
                state = RuntimeState(key="worker")
                db.add(state)
            state.value = heartbeat
        for op in db.scalars(
            select(Operation)
            .where(Operation.status == "running", Operation.lease_until < now())
            .with_for_update(skip_locked=True)
        ).all():
            op.status = "queued" if registry()["methods"][op.method]["effect"] == "read" else "uncertain"
            op.execution_token = None
            op.error = {
                "code": "lease_expired",
                "message": "Worker stopped before recording a confirmed response",
            }
            record(db, "worker", "operation.recovered", op.id, {"status": op.status})
        tick(db)
        paused = db.get(RuntimeState, "paused")
        if paused and paused.value.get("enabled"):
            return False
        op = db.scalar(
            select(Operation)
            .where(Operation.status == "queued", Operation.run_at <= now())
            .order_by(Operation.run_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not op:
            return False
        if registry()["methods"][op.method]["effect"] == "write" and op.approved_digest != op.digest:
            op.status = "draft"
            return False
        try:
            check_target(op.payload)
        except ValueError:
            op.status = "failed"
            op.error = {"code": "target_not_allowed"}
            return False
        op.status = "running"
        op.started_at = now()
        op.lease_until = now() + timedelta(seconds=settings().lease_seconds)
        op.attempts += 1
        execution_token = uid()
        op.execution_token = execution_token
        op_id = op.id
    status = "succeeded"
    result = None
    error = None
    retry_at = None
    try:
        with Session() as db:
            op = db.get(Operation, op_id)
            result = api.call(op.method, op.payload, op.attachments, db)
    except TelegramError as e:
        if e.code == 429 and e.retry_after:
            status = "queued"
            retry_at = now() + timedelta(seconds=max(1, int(e.retry_after)))
        else:
            status = "failed"
        error = {"code": e.code, "message": redact(e.description)}
    except (httpx.HTTPError, OSError) as e:
        status = "uncertain"
        error = {"code": "transport_error", "message": type(e).__name__}
    except Exception as e:
        status = "uncertain"
        error = {"code": "internal_error", "message": type(e).__name__}
    with Session.begin() as db:
        op = db.get(Operation, op_id, with_for_update=True)
        # Never overwrite another recovery decision with an expired worker response.
        if op.status != "running" or op.execution_token != execution_token:
            return True
        op.status = status
        op.result = redact(result)
        op.error = error
        op.lease_until = None
        if status == "succeeded" and op.method == "getStickerSet":
            from .media import index_pack

            index_pack(db, result)
        if retry_at:
            op.run_at = retry_at
        else:
            op.finished_at = now()
        record(
            db,
            "worker",
            "operation." + status,
            op.id,
            {"method": op.method, "attempt": op.attempts, "error": error},
        )
    log.info("operation_finished", extra={"operation_id": op_id, "status": status})
    return True


def run():
    settings().check()
    from .logging_setup import setup

    setup()
    api = Telegram()
    while True:
        try:
            cycle(api)
        except Exception as e:
            log.error("worker_cycle_failed", extra={"error_type": type(e).__name__})
            try:
                with Session.begin() as db:
                    record(db, "worker", "worker.failed", details={"error_type": type(e).__name__})
            except Exception:
                pass  # Database failures remain visible in structured process logs.
        time.sleep(settings().poll_interval)


if __name__ == "__main__":
    run()
