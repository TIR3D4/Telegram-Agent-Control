from datetime import timedelta
import base64
import pytest
from tac.db import now, Session, AgentGrant, Operation
from tac.worker import cycle
from conftest import FakeTelegram
from test_operations import create, approve


def grant(client, owner, **overrides):
    body = {
        "name": "Scoped test agent",
        "chats": ["@test_channel"],
        "expires_at": (now() + timedelta(days=1)).isoformat(),
        **overrides,
    }
    r = client.post("/v1/agents", headers=owner, json=body)
    assert r.status_code == 201, r.text
    return r.json()["grant"], {"Authorization": "Bearer " + r.json()["credential"]} if r.json()[
        "credential"
    ] else None


def change(client, owner, action, parameters, actor=None):
    r = client.post(
        "/v1/admin/requests", headers=actor or owner, json={"action": action, "parameters": parameters}
    )
    assert r.status_code == 201, r.text
    req = r.json()
    assert (
        client.post(
            f"/v1/admin/requests/{req['id']}/approve", headers=owner, json={"expected_digest": req["digest"]}
        ).status_code
        == 200
    )
    return client.post(f"/v1/admin/requests/{req['id']}/execute", headers=owner)


def test_agent_scope_method_channel_and_resource_isolation(client, owner):
    a, ah = grant(client, owner)
    b, bh = grant(client, owner)
    op = create(client, ah).json()
    assert (
        create(
            client, ah, method="setWebhook", payload={"url": "https://example.com"}, key="denied-admin"
        ).status_code
        == 403
    )
    assert (
        create(client, ah, payload={"chat_id": -100123456789, "text": "no"}, key="denied-chat").status_code
        == 403
    )
    assert client.get("/v1/operations/" + op["id"], headers=bh).status_code == 404
    assert not client.get("/v1/operations", headers=bh).json()
    assert (
        create(client, bh).status_code == 404
    )  # A guessed idempotency key cannot disclose another agent's record.
    assert client.post("/v1/operations/" + op["id"] + "/cancel", headers=bh).status_code == 404
    assert approve(client, ah, op).status_code == 403
    assert client.get("/v1/agents", headers=ah).status_code == 403


def test_read_grant_can_queue_reads_but_cannot_write(client, owner):
    g, h = grant(client, owner, preset="READ")
    assert create(client, h).status_code == 403
    assert create(client, h, method="getMe", payload={}).status_code == 201
    assert client.post("/v1/assets", headers=h, files={"file": ("a.txt", b"a")}).status_code == 403


def test_revocation_stops_queued_work_and_invalidates_credential(client, owner):
    g, h = grant(client, owner)
    op = create(client, h).json()
    assert approve(client, owner, op).status_code == 200
    assert change(client, owner, "revoke_credential", {"agent_id": g["id"]}).status_code == 200
    assert client.get("/v1/system", headers=h).status_code == 401
    fake = FakeTelegram()
    cycle(fake)
    assert not fake.calls
    with Session() as db:
        assert db.get(Operation, op["id"]).status == "failed"


def test_rotation_is_independent_one_use_and_preserves_identity(client, owner):
    g, h = grant(client, owner)
    r = client.post(
        "/v1/admin/requests",
        headers=h,
        json={"action": "rotate_credential", "parameters": {"agent_id": g["id"]}},
    ).json()
    assert (
        client.post(
            f"/v1/admin/requests/{r['id']}/approve", headers=h, json={"expected_digest": r["digest"]}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/v1/admin/requests/{r['id']}/approve", headers=owner, json={"expected_digest": "wrong"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/v1/admin/requests/{r['id']}/approve", headers=owner, json={"expected_digest": r["digest"]}
        ).status_code
        == 200
    )
    out = client.post(f"/v1/admin/requests/{r['id']}/execute", headers=owner)
    assert out.status_code == 200
    assert client.get("/v1/system", headers=h).status_code == 401
    fresh = {"Authorization": "Bearer " + out.json()["credential"]}
    assert client.get("/v1/system", headers=fresh).json()["identity"] == "agent:" + g["id"]
    assert client.post(f"/v1/admin/requests/{r['id']}/execute", headers=owner).status_code == 409
    assert out.json()["credential"] not in client.get("/v1/logs", headers=owner).text


def test_expired_grant_and_approval_fail_closed(client, owner):
    g, h = grant(client, owner)
    op = create(client, h).json()
    approve(client, owner, op)
    with Session.begin() as db:
        db.get(Operation, op["id"]).approved_until = now() - timedelta(seconds=1)
    fake = FakeTelegram()
    cycle(fake)
    assert not fake.calls
    assert client.get("/v1/operations/" + op["id"], headers=h).json()["status"] == "draft"
    with Session.begin() as db:
        db.get(AgentGrant, g["id"]).expires_at = now() - timedelta(seconds=1)
    assert client.get("/v1/system", headers=h).status_code == 401


def test_daily_operation_quota_does_not_charge_idempotent_replays(client, owner):
    _, h = grant(client, owner, daily_operations=1)
    assert create(client, h).status_code == 201
    assert create(client, h).status_code == 201
    assert create(client, h, key="second-operation").status_code == 429


def test_request_quota(client, owner):
    _, h = grant(client, owner, rpm=1)
    assert client.get("/v1/system", headers=h).status_code == 200
    assert client.get("/v1/system", headers=h).status_code == 429


def test_media_ownership_reuse_and_controlled_delete(client, owner):
    _, h = grant(client, owner)
    _, foreign = grant(client, owner)
    data = {"name": "image.txt", "mime": "text/plain", "data_base64": base64.b64encode(b"fixture").decode()}
    a = client.post("/v1/assets/encoded", headers=h, json=data).json()
    assert client.get("/v1/assets/" + a["id"], headers=foreign).status_code == 404
    assert client.get("/v1/assets/" + a["id"] + "/metadata", headers=h).json()["size"] == 7
    assert change(client, owner, "delete_asset", {"asset_id": a["id"]}, h).status_code == 200
    assert client.get("/v1/assets/" + a["id"], headers=h).status_code == 404


def test_referenced_media_cannot_be_deleted(client, owner):
    _, h = grant(client, owner)
    a = client.post("/v1/assets", headers=h, files={"file": ("x.png", b"fixture", "image/png")}).json()
    payload = {
        "method": "sendPhoto",
        "payload": {"chat_id": "@test_channel", "photo": "attach://x"},
        "attachments": {"x": a["id"]},
        "idempotency_key": "referenced-photo",
    }
    assert client.post("/v1/operations", headers=h, json=payload).status_code == 201
    assert change(client, owner, "delete_asset", {"asset_id": a["id"]}, h).status_code == 409


@pytest.mark.parametrize(
    "button",
    [
        {"text": "A", "url": "javascript:alert(1)"},
        {"text": "A", "url": "https://example.com", "callback_data": "x"},
        {"text": "A", "callback_data": "ی" * 40},
        {"text": "A", "url": "https://example.com", "style": "glass"},
    ],
)
def test_keyboard_rejects_unsupported_or_unsafe_buttons(client, agent, button):
    assert client.post("/v1/keyboards/build", headers=agent, json={"rows": [[button]]}).status_code == 422


def test_keyboard_native_styles_and_removal(client, agent):
    r = client.post(
        "/v1/keyboards/build",
        headers=agent,
        json={
            "rows": [
                [
                    {
                        "text": "✅ Open",
                        "url": "https://t.me/test",
                        "style": "primary",
                        "icon_custom_emoji_id": "123",
                    }
                ]
            ]
        },
    )
    assert r.status_code == 200
    assert r.json()["reply_markup"]["inline_keyboard"][0][0]["style"] == "primary"
    assert client.post("/v1/keyboards/build", headers=agent, json={"rows": []}).json()["reply_markup"] == {
        "inline_keyboard": []
    }


def test_foreign_updates_are_not_readable(client, owner):
    from tac.db import Update

    _, h = grant(client, owner, chats=["-100123456789"])
    with Session.begin() as db:
        db.add(Update(id=1, body={"channel_post": {"chat": {"id": -100123456789}, "text": "allowed"}}))
        db.add(Update(id=2, body={"channel_post": {"chat": {"id": -100999999999}, "text": "private"}}))
    r = client.get("/v1/updates", headers=h)
    assert len(r.json()) == 1
    assert "private" not in r.text


def test_trace_and_logs_do_not_include_credentials(client, owner):
    _, h = grant(client, owner)
    r = client.get("/v1/system", headers=h)
    trace = client.get("/v1/traces/" + r.headers["x-trace-id"], headers=h)
    assert trace.status_code == 200 and trace.json()
    assert h["Authorization"].split()[1] not in trace.text


def test_disable_legacy_keys_preserves_scoped_access_and_stops_legacy_work(client, owner, agent, monkeypatch):
    from tac.config import settings

    _, scoped = grant(client, owner)
    operation = create(client, agent).json()
    approve(client, owner, operation)
    monkeypatch.setattr(settings(), "legacy_agent_keys_enabled", False)
    assert client.get("/v1/system", headers=agent).status_code == 401
    assert client.get("/v1/system", headers=scoped).status_code == 200
    fake = FakeTelegram()
    cycle(fake)
    assert not fake.calls
    assert client.get("/v1/operations/" + operation["id"], headers=owner).json()["status"] == "failed"
