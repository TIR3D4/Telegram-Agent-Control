import sys
from sqlalchemy import select
from .db import Session, RuntimeState, Operation, record


def restored():
    with Session.begin() as db:
        state = db.get(RuntimeState, "paused")
        if not state:
            state = RuntimeState(key="paused")
            db.add(state)
        state.value = {"enabled": True}
        for op in db.scalars(select(Operation).where(Operation.status == "running")):
            op.status = "uncertain"
            op.error = {"code": "restored_backup", "message": "Reconcile with Telegram before retrying"}
        record(db, "maintenance", "backup.restored")


def prune():
    from datetime import timedelta
    from sqlalchemy import delete
    from .db import Audit, RateBucket, now
    from .config import settings

    with Session.begin() as db:
        db.execute(
            delete(RateBucket).where(
                RateBucket.key.in_(select(RateBucket.key).where(RateBucket.expires_at < now()).limit(1000))
            )
        )
        expired = (
            select(Audit.id)
            .where(
                Audit.action == "http.request", Audit.at < now() - timedelta(days=settings().retention_days)
            )
            .limit(1000)
        )
        db.execute(delete(Audit).where(Audit.id.in_(expired)))
    # Approval/operation audit history and idempotency records are retained.


def backup_record():
    import json

    data = json.loads(sys.stdin.read(8192))
    with Session.begin() as db:
        state = db.get(RuntimeState, "backup")
        if not state:
            state = RuntimeState(key="backup")
            db.add(state)
        state.value = data
        record(db, "operator", "backup.verified", details={"name": data["name"], "commit": data["commit"]})


def consume_restore(id):
    from .control_api import checked_request

    with Session.begin() as db:
        r = checked_request(db, id)
        if r.action != "restore_backup":
            raise ValueError("Not a restore approval")
        r.status = "operator-consumed"
        record(db, "operator", "restore.authorized", id)
        name = r.parameters["backup_name"]
    print(name)


if __name__ == "__main__":
    action = sys.argv[1:]
    if action in (["restored"], ["pause-upgrade"]):
        restored()
    elif action == ["backup-record"]:
        backup_record()
    elif action == ["prune"]:
        prune()
    elif len(action) == 2 and action[0] == "consume-restore":
        consume_restore(action[1])
    else:
        raise SystemExit("Unknown maintenance action")
