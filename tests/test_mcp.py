import httpx
import pytest


@pytest.mark.parametrize(
    "status,body", [(502, b"<html>upstream unavailable</html>"), (503, b"[]"), (200, b"")]
)
def test_gateway_malformed_response_is_safe_and_never_retried(monkeypatch, status, body):
    from tac import mcp_server

    requests = []
    original = httpx.Client

    def respond(request):
        requests.append(request)
        return httpx.Response(status, content=body)

    monkeypatch.setattr(
        mcp_server.httpx, "Client", lambda **kw: original(**kw, transport=httpx.MockTransport(respond))
    )
    result = mcp_server.call("POST", "/v1/operations", {"idempotency_key": "gateway-test"})
    assert result["ok"] is False
    assert result["error"]["code"] == "gateway_invalid_response"
    assert result["error"]["status"] == status
    assert "original idempotency key" in result["error"]["retry"]
    assert len(requests) == 1
    assert "upstream unavailable" not in str(result)


def rpc(client, agent, method, params=None, id=1):
    return client.post(
        "/mcp/",
        headers={**agent, "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}},
    )


def test_mcp_requires_auth_and_exposes_no_approval_tool(client, agent):
    assert client.post("/mcp/", json={}).status_code == 401
    r = rpc(
        client,
        agent,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "tac-test", "version": "1"},
        },
    )
    assert r.status_code == 200, r.text
    r = rpc(client, agent, "tools/list")
    assert r.status_code == 200, r.text
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert {"submit_operation", "method_schema", "inspect_logs", "emoji_image"} <= names
    assert not any("approv" in n for n in names)
