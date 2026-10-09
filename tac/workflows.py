import re
from datetime import timedelta, datetime, timezone
from zoneinfo import ZoneInfo
from croniter import croniter
from sqlalchemy import select
from .db import Workflow, WorkflowRun, Operation, now, record
from .operations import submit, utc
from .registry import validate

REF = re.compile(r"^\$steps\.(\d+)\.result(?:\.(.+))?$")


def resolve(value, results):
    if isinstance(value, str) and (m := REF.fullmatch(value)):
        index = int(m[1])
        if index >= len(results):
            raise ValueError("Reference must point to a completed previous step")
        v = results[index]
        for k in (m[2] or "").split(".") if m[2] else []:
            v = v[int(k)] if isinstance(v, list) else v[k]
        return v
    if isinstance(value, dict):
        return {k: resolve(v, results) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, results) for v in value]
    return value


def validate_steps(steps):
    if not 1 <= len(steps) <= 30:
        raise ValueError("Workflow needs 1–30 steps")
    for i, step in enumerate(steps):
        if set(step) - {"method", "payload", "attachments", "delay_seconds"}:
            raise ValueError("Unknown workflow step field")
        if not 0 <= step.get("delay_seconds", 0) <= 31536000:
            raise ValueError("Invalid delay")
        # Structural validation deferred for result references; execute still validates resolved types.
        payload = step["payload"]

        def mock(v):
            if isinstance(v, str) and (m := REF.fullmatch(v)):
                if int(m[1]) >= i:
                    raise ValueError("Only previous step references are allowed")
                return 1
            if isinstance(v, dict):
                return {k: mock(x) for k, x in v.items()}
            if isinstance(v, list):
                return [mock(x) for x in v]
            return v

        from .registry import registry

        if step["method"] not in registry()["methods"]:
            raise ValueError("Unknown workflow method")
        # Full validation for concrete payloads. Template field types checked after binding.
        if "$steps." not in str(payload):
            validate(step["method"], payload)
        else:
            mock(payload)
        from .operations import check_target

        if "$steps." in str(payload.get("chat_id", "")):
            raise ValueError("Target chat must be fixed at approval")
        check_target(payload)


def next_time(trigger, tz, after=None):
    ZoneInfo(tz)
    after = utc(after or now())
    if trigger["type"] == "once":
        target = datetime.fromisoformat(trigger["at"].replace("Z", "+00:00"))
        if target.tzinfo is None:
            raise ValueError("Schedule time must include UTC offset")
        return utc(target)
    if trigger["type"] == "cron":
        return (
            croniter(trigger["expression"], after.astimezone(ZoneInfo(tz)))
            .get_next(datetime)
            .astimezone(timezone.utc)
        )
    if trigger["type"] == "update":
        return None
    raise ValueError("Unknown trigger type")


def start_run(db, w, key):
    if not w.active or w.approved_digest != w.digest or w.runs_count >= w.max_runs:
        return
    if db.scalar(
        select(WorkflowRun).where(WorkflowRun.workflow_id == w.id, WorkflowRun.occurrence_key == key)
    ):
        return
    run = WorkflowRun(workflow_id=w.id, occurrence_key=key, steps=w.steps)
    db.add(run)
    db.flush()
    w.runs_count += 1
    record(db, "scheduler", "workflow.started", run.id, {"workflow_id": w.id})
    return run


def tick(db):
    due = db.scalars(
        select(Workflow)
        .where(Workflow.active.is_(True), Workflow.next_run <= now())
        .with_for_update(skip_locked=True)
    ).all()
    for w in due:
        occurrence = utc(w.next_run)
        # Coalesce missed cron occurrences to one; never replay a backlog.
        start_run(db, w, occurrence.isoformat())
        w.next_run = next_time(w.trigger, w.timezone) if w.trigger["type"] == "cron" else None
        if w.runs_count >= w.max_runs:
            w.active = False
    runs = db.scalars(
        select(WorkflowRun).where(WorkflowRun.status == "running").with_for_update(skip_locked=True)
    ).all()
    for run in runs:
        w = db.get(Workflow, run.workflow_id)
        if not w or w.approved_digest != w.digest:
            run.status = "paused"
            continue
        ops = db.scalars(
            select(Operation).where(Operation.workflow_run_id == run.id).order_by(Operation.step_index)
        ).all()
        if ops and ops[-1].status in ("failed", "uncertain", "cancelled"):
            run.status = ops[-1].status
            continue
        if ops and ops[-1].status != "succeeded":
            continue
        if len(ops) == len(run.steps):
            run.status = "succeeded"
            continue
        step = run.steps[len(ops)]
        try:
            payload = resolve(step["payload"], [o.result for o in ops])
            at = now() + timedelta(seconds=step.get("delay_seconds", 0))
            op = submit(
                db,
                step["method"],
                payload,
                step.get("attachments", {}),
                f"workflow:{run.id}:{len(ops)}",
                "workflow",
                at,
            )
            op.workflow_run_id = run.id
            op.step_index = len(ops)
            op.approved_digest = op.digest
            op.approved_by = "workflow-owner-grant"
            op.status = "queued"
            run.cursor = len(ops)
        except (ValueError, KeyError, IndexError, TypeError) as e:
            run.status = "failed"
            record(db, "scheduler", "workflow.invalid", run.id, {"error": str(e)})


def on_update(db, update):
    for w in db.scalars(select(Workflow).where(Workflow.active.is_(True)).with_for_update()).all():
        if w.trigger.get("type") != "update":
            continue
        event = w.trigger.get("event")
        if event in update:
            target = update[event].get("chat", {}).get("id") if isinstance(update[event], dict) else None
            if str(target) == str(w.trigger.get("chat_id")):
                start_run(db, w, "update:" + str(update["update_id"]))
