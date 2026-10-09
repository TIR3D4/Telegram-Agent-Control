from concurrent.futures import ThreadPoolExecutor
import threading
import time
from sqlalchemy import text
import pytest
from tac.db import engine, Session, Operation, RuntimeState, now
from tac.worker import cycle
from test_operations import create, approve
from conftest import FakeTelegram


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Production locking test requires PostgreSQL")
def test_two_workers_never_send_same_operation(client, agent, owner):
    op = create(client, agent).json()
    approve(client, owner, op)
    with Session.begin() as db:
        db.add(RuntimeState(key="worker", value={"heartbeat": now().isoformat()}))
    fake = FakeTelegram()
    barrier = threading.Barrier(2)

    def run():
        barrier.wait()
        return cycle(fake)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(run) for _ in range(2)]
        for f in results:
            f.result(timeout=20)
    assert len(fake.calls) == 1
    with Session() as db:
        assert db.get(Operation, op["id"]).status == "succeeded"


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Production locking test requires PostgreSQL")
def test_recovery_lock_fences_a_late_worker_response(client, agent, owner):
    op = create(client, agent).json()
    approve(client, owner, op)
    entered, release = threading.Event(), threading.Event()

    class SlowTelegram(FakeTelegram):
        def call(self, *args, **kwargs):
            entered.set()
            assert release.wait(10)
            return super().call(*args, **kwargs)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(cycle, SlowTelegram())
        assert entered.wait(10)
        with Session.begin() as db:
            current = db.get(Operation, op["id"], with_for_update=True)
            current.status = "uncertain"
            current.execution_token = None
            db.flush()
            release.set()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                db.execute(text("SELECT pg_stat_clear_snapshot()"))
                blocked = db.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                        "AND pid<>pg_backend_pid() AND wait_event_type='Lock'"
                    )
                )
                if blocked:
                    break
                time.sleep(0.02)
            else:
                raise AssertionError("Expected worker completion to wait for recovery transaction")
        future.result(timeout=10)
    with Session() as db:
        assert db.get(Operation, op["id"]).status == "uncertain"


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Atomic quota contention requires PostgreSQL")
def test_agent_request_quota_is_atomic(client, owner):
    from test_governance import grant
    from tac.security import authenticate
    from fastapi import HTTPException

    _, headers = grant(client, owner, rpm=3)
    token = headers["Authorization"].split()[1]
    barrier = threading.Barrier(8)

    def attempt():
        barrier.wait()
        try:
            authenticate(token)
            return 200
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: attempt(), range(8)))
    assert results.count(200) == 3
    assert results.count(429) == 5
