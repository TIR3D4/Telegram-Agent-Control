import os
from datetime import timedelta
from sqlalchemy import select
from tac.db import Session, Operation, WorkflowRun, now
from tac.worker import cycle
from conftest import FakeTelegram


def workflow(client, agent, owner, trigger=None):
    steps = [
        {"method": "sendMessage", "payload": {"chat_id": "@test_channel", "text": "scheduled"}},
        {
            "method": "pinChatMessage",
            "payload": {"chat_id": "@test_channel", "message_id": "$steps.0.result.message_id"},
        },
        {
            "method": "unpinChatMessage",
            "delay_seconds": 86400,
            "payload": {"chat_id": "@test_channel", "message_id": "$steps.0.result.message_id"},
        },
    ]
    r = client.post(
        "/v1/workflows",
        headers=agent,
        json={
            "name": "Publish pin unpin",
            "steps": steps,
            "trigger": trigger or {"type": "once", "at": (now() - timedelta(seconds=1)).isoformat()},
            "max_runs": 1,
        },
    )
    assert r.status_code == 201, r.text
    w = r.json()
    assert (
        client.post(
            "/v1/workflows/" + w["id"] + "/approve", headers=owner, json={"expected_digest": w["digest"]}
        ).status_code
        == 200
    )
    return w


def test_durable_steps_and_delayed_unpin(client, agent, owner):
    workflow(client, agent, owner)
    fake = FakeTelegram()
    cycle(fake)
    cycle(fake)
    cycle(fake)
    assert [m for m, p in fake.calls] == ["sendMessage", "pinChatMessage"]
    assert fake.calls[1][1]["message_id"] == 42
    with Session.begin() as db:
        op = db.scalar(select(Operation).where(Operation.method == "unpinChatMessage"))
        op.run_at = now() - timedelta(seconds=1)
    cycle(fake)
    cycle(fake)
    with Session() as db:
        assert db.scalar(select(WorkflowRun)).status == "succeeded"
    assert len(fake.calls) == 3


def test_pause_stops_future_steps(client, agent, owner):
    w = workflow(client, agent, owner)
    fake = FakeTelegram()
    cycle(fake)
    client.post("/v1/workflows/" + w["id"] + "/pause", headers=agent)
    cycle(fake)
    assert len(fake.calls) == 1


def test_webhook_dedup_and_event_trigger(client, agent, owner):
    workflow(
        client, agent, owner, trigger={"type": "update", "event": "channel_post", "chat_id": -100123456789}
    )
    h = {"X-Telegram-Bot-Api-Secret-Token": os.environ["TAC_WEBHOOK_SECRET"]}
    body = {"update_id": 14, "channel_post": {"chat": {"id": -100123456789}, "message_id": 4}}
    assert client.post("/v1/webhook", json=body).status_code == 401
    assert client.post("/v1/webhook", headers=h, json=body).status_code == 200
    assert client.post("/v1/webhook", headers=h, json=body).json()["duplicate"]
    with Session() as db:
        assert len(db.scalars(select(WorkflowRun)).all()) == 1


def test_future_reference_rejected(client, agent):
    r = client.post(
        "/v1/workflows",
        headers=agent,
        json={
            "name": "bad",
            "steps": [
                {
                    "method": "pinChatMessage",
                    "payload": {"chat_id": "@test_channel", "message_id": "$steps.0.result.message_id"},
                }
            ],
            "trigger": {"type": "once", "at": now().isoformat()},
        },
    )
    assert r.status_code == 422
