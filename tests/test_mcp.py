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
