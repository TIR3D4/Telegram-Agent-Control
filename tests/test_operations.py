from datetime import timedelta
import httpx
from tac.db import Session, Operation, now
from tac.worker import cycle
from tac.telegram import TelegramError
from conftest import FakeTelegram


def create(client, agent, method="sendMessage", payload=None, key="test-key-0001", run_at=None):
    return client.post(
        "/v1/operations",
        headers=agent,
        json={
            "method": method,
            "payload": payload if payload is not None else {"chat_id": "@test_channel", "text": "سلام"},
            "idempotency_key": key,
            "run_at": run_at,
        },
    )


def approve(client, owner, o):
    return client.post(
        "/v1/operations/" + o["id"] + "/approve", headers=owner, json={"expected_digest": o["digest"]}
    )


def test_write_approval_and_idempotency(client, agent, owner):
    first = create(client, agent).json()
    assert first["status"] == "draft"
    fake = FakeTelegram()
    assert cycle(fake) is False
    assert not fake.calls
    assert (
        client.post(
            "/v1/operations/" + first["id"] + "/approve",
            headers=agent,
            json={"expected_digest": first["digest"]},
        ).status_code
        == 403
    )
    assert approve(client, owner, first).status_code == 200
    assert cycle(fake)
    assert len(fake.calls) == 1
    result = client.get("/v1/operations/" + first["id"], headers=agent).json()
    assert result["status"] == "succeeded"
    assert result["message_links"] == ["https://t.me/test_channel/42"]
    assert create(client, agent).json()["id"] == first["id"]
    assert not cycle(fake)
    assert len(fake.calls) == 1
    assert create(client, agent, payload={"chat_id": "@test_channel", "text": "other"}).status_code == 409


def test_edit_revokes_approval(client, agent, owner):
    op = create(client, agent).json()
    approve(client, owner, op)
    changed = client.patch(
        "/v1/operations/" + op["id"],
        headers=agent,
        json={"expected_digest": op["digest"], "payload": {"chat_id": "@test_channel", "text": "changed"}},
    ).json()
    assert changed["status"] == "draft"
    assert changed["approved_digest"] is None
    assert approve(client, owner, op).status_code == 409
    assert not cycle(FakeTelegram())


def test_schedule_cancel_and_disallowed_target(client, agent, owner):
    op = create(client, agent, run_at=(now() + timedelta(hours=1)).isoformat()).json()
    approve(client, owner, op)
    assert not cycle(FakeTelegram())
    assert client.post("/v1/operations/" + op["id"] + "/cancel", headers=agent).status_code == 200
    assert (
        create(
            client, agent, payload={"chat_id": "@other_channel", "text": "x"}, key="not-allowed"
        ).status_code
        == 422
    )


def test_timeout_is_uncertain_and_never_blind_retries(client, agent, owner):
    op = create(client, agent).json()
    approve(client, owner, op)
    fake = FakeTelegram(error=httpx.ReadTimeout("timeout"))
    cycle(fake)
    assert len(fake.calls) == 1
    assert client.get("/v1/operations/" + op["id"], headers=agent).json()["status"] == "uncertain"
    cycle(fake)
    assert len(fake.calls) == 1
    assert (
        client.post(
            "/v1/operations/" + op["id"] + "/resolve",
            headers=owner,
            json={"status": "succeeded", "result": {"message_id": 42}, "note": "Verified in test channel"},
        ).status_code
        == 200
    )


def test_429_requeues_but_permission_errors_stop(client, agent, owner):
    op = create(client, agent).json()
    approve(client, owner, op)
    cycle(FakeTelegram(error=TelegramError(429, "Too many requests", 30)))
    data = client.get("/v1/operations/" + op["id"], headers=agent).json()
    assert data["status"] == "queued"
    assert data["attempts"] == 1
    with Session.begin() as db:
        db.get(Operation, op["id"]).run_at = now() - timedelta(seconds=1)
    cycle(FakeTelegram(error=TelegramError(403, "No permissions")))
    assert client.get("/v1/operations/" + op["id"], headers=agent).json()["status"] == "failed"


def test_worker_crash_recovery(client, agent, owner):
    op = create(client, agent).json()
    approve(client, owner, op)
    with Session.begin() as db:
        o = db.get(Operation, op["id"])
        o.status = "running"
        o.lease_until = now() - timedelta(seconds=5)
    fake = FakeTelegram()
    cycle(fake)
    assert not fake.calls
    assert client.get("/v1/operations/" + op["id"], headers=agent).json()["status"] == "uncertain"


def test_reads_queue_and_audit_is_redacted(client, agent):
    op = create(client, agent, method="getMe", payload={}).json()
    assert op["status"] == "queued"
    cycle(FakeTelegram(result={"id": 1, "is_bot": True}))
    logs = client.get("/v1/logs", headers=agent).json()
    assert any(entry["action"] == "operation.succeeded" for entry in logs)
    assert client.get("/v1/database/overview", headers=agent).status_code == 200
    assert client.get("/v1/logs").status_code == 401


def test_asset_binding(client, agent, owner):
    a = client.post("/v1/assets", headers=agent, files={"file": ("x.jpg", b"photo", "image/jpeg")}).json()
    bad = create(
        client, agent, method="sendPhoto", payload={"chat_id": "@test_channel", "photo": "attach://photo"}
    )
    assert bad.status_code == 422
    result = client.post(
        "/v1/operations",
        headers=agent,
        json={
            "method": "sendPhoto",
            "payload": {"chat_id": "@test_channel", "photo": "attach://photo"},
            "attachments": {"photo": a["id"]},
            "idempotency_key": "asset-operation",
        },
    )
    assert result.status_code == 201
