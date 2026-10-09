from concurrent.futures import ThreadPoolExecutor
import threading
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
