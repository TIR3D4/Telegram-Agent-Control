"""Every advertised tool is invoked over MCP against the real shared REST app.

No Telegram credential/network is used: emoji previews are pre-rendered fixtures.
"""

import base64
import json
from datetime import timedelta
import httpx
import pytest
from sqlalchemy import select
from tac.db import Session, Emoji, Operation, now
from test_governance import grant
from test_mcp import rpc

CASES = {
    "capabilities": {"query": "send", "limit": 2},
    "method_schema": {"method": "sendPhoto"},
    "type_schema": {"name": "InlineKeyboardButton"},
    "validate_request": {"method": "getMe", "payload": {}},
    "submit_operation": {"method": "getMe", "payload": {}, "idempotency_key": "protocol-read"},
    "operation_status": {"operation_id": "$operation"},
    "inspect_system": {},
    "inspect_database": {},
    "inspect_logs": {},
    "create_automation": {
        "name": "new",
        "steps": [{"method": "sendMessage", "payload": {"chat_id": "@test_channel", "text": "planned"}}],
        "trigger": {"type": "once", "at": "$time"},
    },
    "cancel_operation": {"operation_id": "$operation"},
    "search_emoji": {"query": "fixture"},
    "prepare_emoji_preview": {"emoji_id": "123"},
    "label_emoji": {"emoji_id": "123", "description": "blue fixture", "tags": ["blue"]},
    "bind_emoji": {"role": "support", "emoji_id": "123"},
    "emoji_image": {"asset_id": "$asset"},
    "list_operations": {},
    "draft_text": {"chat_id": "@test_channel", "text": "draft", "idempotency_key": "protocol-text"},
    "draft_media": {
        "kind": "photo",
        "chat_id": "@test_channel",
        "media": "attach://photo",
        "attachments": {"photo": "$asset"},
        "idempotency_key": "protocol-media",
    },
    "revise_draft": {
        "operation_id": "$operation",
        "expected_digest": "$digest",
        "payload": {"chat_id": "@test_channel", "text": "revision"},
    },
    "preview_post": {"operation_id": "$operation"},
    "duplicate_post": {"operation_id": "$operation", "idempotency_key": "protocol-duplicate"},
    "retry_failed": {"operation_id": "$failed", "idempotency_key": "protocol-retry"},
    "upload_media": {
        "name": "text.txt",
        "mime": "text/plain",
        "data_base64": base64.b64encode(b"test").decode(),
    },
    "list_media": {},
    "media_metadata": {"asset_id": "$asset"},
    "build_keyboard": {"rows": [[{"text": "Open", "url": "https://t.me/test", "style": "primary"}]]},
    "list_workflows": {},
    "revise_workflow": {
        "workflow_id": "$workflow",
        "expected_digest": "$workflow_digest",
        "name": "revised",
        "steps": [{"method": "sendMessage", "payload": {"chat_id": "@test_channel", "text": "planned"}}],
        "trigger": {"type": "once", "at": "$time"},
    },
    "pause_workflow": {"workflow_id": "$workflow"},
    "workflow_history": {"workflow_id": "$workflow"},
    "inspect_channels": {},
    "inspect_accounts": {},
    "read_updates": {},
    "inspect_metrics": {},
    "inspect_settings": {},
    "inspect_trace": {"trace_id": "$trace"},
    "request_maintenance": {"action": "pause_execution", "parameters": {"enabled": True}},
    "maintenance_status": {},
    "database_status": {},
    "channel_analytics": {"chat_id": "@test_channel"},
    "validate_settings": {"timezone": "Asia/Tehran", "upload_limit_mb": 50, "retention_days": 90},
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_tool_reaches_shared_gateway(client, owner, monkeypatch, name):
    _, h = grant(client, owner, rpm=1000)
    asset = client.post(
        "/v1/assets", headers=h, files={"file": ("fixture.png", b"png-fixture", "image/png")}
    ).json()
    body = {
        "method": "sendMessage",
        "payload": {"chat_id": "@test_channel", "text": "fixture"},
        "idempotency_key": "protocol-fixture",
    }
    op = client.post("/v1/operations", headers=h, json=body).json()
    failed = client.post(
        "/v1/operations", headers=h, json={**body, "idempotency_key": "failed-fixture"}
    ).json()
    at = (now() + timedelta(days=1)).isoformat()
    w = client.post(
        "/v1/workflows",
        headers=h,
        json={
            "name": "fixture",
            "steps": [{"method": body["method"], "payload": body["payload"]}],
            "trigger": {"type": "once", "at": at},
            "max_runs": 1,
        },
    ).json()
    with Session.begin() as db:
        f = db.get(Operation, failed["id"])
        f.status = "failed"
        f.error = {"code": 400}
        db.add(
            Emoji(
                id="123",
                pack="fixture",
                alt="✅",
                file_id="mock",
                format="webp",
                preview_id=asset["id"],
                labels={"description": "fixture"},
                reviewed=True,
            )
        )
    original = httpx.Client

    def respond(request):
        response = client.request(
            request.method,
            request.url.path + ("?" + request.url.query.decode() if request.url.query else ""),
            headers=dict(request.headers),
            content=request.content,
        )
        return httpx.Response(response.status_code, content=response.content, headers=dict(response.headers))

    def factory(**kwargs):
        return original(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr("tac.mcp_server.httpx.Client", factory)

    def get(url, **kwargs):
        with factory() as remote:
            return remote.get(url, **kwargs)

    monkeypatch.setattr("tac.mcp_server.httpx.get", get)
    discovery = rpc(client, h, "tools/list").json()["result"]["tools"]
    assert {t["name"] for t in discovery} == set(CASES), "Document/test newly advertised tools"
    args = json.dumps(CASES[name])
    replacements = {
        "$operation": op["id"],
        "$digest": op["digest"],
        "$failed": failed["id"],
        "$asset": asset["id"],
        "$workflow": w["id"],
        "$workflow_digest": w["digest"],
        "$time": at,
        "$trace": op["trace_id"],
    }
    for key, value in replacements.items():
        args = args.replace('"' + key + '"', json.dumps(value))
    result = rpc(client, h, "tools/call", {"name": name, "arguments": json.loads(args)}).json()["result"]
    assert not result.get("isError"), result
    if name == "emoji_image":
        assert result["content"][0]["type"] == "image"
    else:
        assert "structuredContent" in result, name
        value = result["structuredContent"]
        if "data" in value:
            value = value["data"]
        assert not isinstance(value, dict) or value.get("ok") is not False, value
    # None of these tools can approve/send content.
    with Session() as db:
        assert not db.scalars(select(Operation).where(Operation.approved_by.is_not(None))).all()
