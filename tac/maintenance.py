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


if __name__ == "__main__":
    if sys.argv[1:] == ["restored"]:
        restored()
