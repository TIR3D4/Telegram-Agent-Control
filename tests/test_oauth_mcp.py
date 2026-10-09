from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import jwt
import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from tac.config import settings
from tac.db import now
from test_governance import grant
from test_mcp import rpc


@pytest.fixture
def issuer(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    conf = settings()
    monkeypatch.setattr(conf, "oauth_issuer", "https://identity.example.test")
    monkeypatch.setattr(conf, "oauth_jwks_url", "https://identity.example.test/keys")
    monkeypatch.setattr(conf, "oauth_audience", "https://tac.example.test/mcp")
    monkeypatch.setattr(conf, "public_url", "https://tac.example.test")
    monkeypatch.setattr(
        "tac.oauth.jwks_client",
        lambda _: SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())
        ),
    )

    def mint(**kwargs):
        t = int(now().timestamp())
        body = {
            "sub": "agent-subject",
            "iss": conf.oauth_issuer,
            "aud": conf.oauth_audience,
            "iat": t,
            "exp": t + 300,
            "scope": "system:read posts:read telegram:read",
            **kwargs,
        }
        return jwt.encode(body, key, algorithm="RS256", headers={"kid": "fixture"})

    return mint


def test_oauth_discovery_and_subject_mapping(client, owner, issuer):
    g, _ = grant(client, owner, oauth_subject="agent-subject")
    meta = client.get("/.well-known/oauth-protected-resource").json()
    assert meta["resource"] == settings().oauth_audience
    assert meta["authorization_servers"] == [settings().oauth_issuer]
    token = issuer()
    h = {"Authorization": "Bearer " + token}
    assert client.get("/v1/system", headers=h).json()["identity"] == "agent:" + g["id"]
    # The local grant is OPERATE but this OAuth token only consents to reads.
    assert client.post("/v1/assets", headers=h, files={"file": ("x", b"x")}).status_code == 403
    assert "resource_metadata=" in client.get("/v1/system").headers["www-authenticate"]


@pytest.mark.parametrize(
    "override",
    [
        {"aud": "https://other.example/mcp"},
        {"iss": "https://evil.example"},
        {"exp": 1},
        {"sub": "unmapped"},
        {"scope": ["system:read"]},
        {"exp": 9999999999},
    ],
)
def test_invalid_oauth_claims_rejected(client, owner, issuer, override):
    grant(client, owner, oauth_subject="agent-subject")
    assert (
        client.get("/v1/system", headers={"Authorization": "Bearer " + issuer(**override)}).status_code == 401
    )


def test_mcp_refuses_owner_credentials_and_bad_origin(client, owner, agent):
    assert rpc(client, owner, "tools/list").status_code == 403
    r = client.post(
        "/mcp/",
        headers={**agent, "Accept": "application/json, text/event-stream", "Origin": "https://evil.example"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert r.status_code in {400, 403}


def bridge(monkeypatch, client):
    original = httpx.Client

    def respond(request):
        r = client.request(
            request.method,
            request.url.path + ("?" + request.url.query.decode() if request.url.query else ""),
            headers=dict(request.headers),
            content=request.content,
        )
        return httpx.Response(r.status_code, json=r.json(), headers=dict(r.headers))

    monkeypatch.setattr(
        "tac.mcp_server.httpx.Client",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(respond)),
    )


def test_protocol_preserves_two_independent_identities(client, owner, monkeypatch):
    a, ah = grant(client, owner)
    b, bh = grant(client, owner, preset="READ")
    bridge(monkeypatch, client)

    def invoke(h):
        return rpc(client, h, "tools/call", {"name": "inspect_system", "arguments": {}}).json()["result"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(invoke, [ah, bh]))
    import json

    assert "agent:" + a["id"] in json.dumps(results[0])
    assert "agent:" + b["id"] not in json.dumps(results[0])
    assert "agent:" + b["id"] in json.dumps(results[1])
    denied = rpc(
        client,
        bh,
        "tools/call",
        {
            "name": "draft_text",
            "arguments": {"chat_id": "@test_channel", "text": "x", "idempotency_key": "mcp-denied-write"},
        },
    )
    assert "403" in denied.text


def test_tool_schemas_and_structured_response(client, owner, monkeypatch):
    _, h = grant(client, owner)
    bridge(monkeypatch, client)
    discovery = rpc(client, h, "tools/list").json()["result"]["tools"]
    names = {t["name"] for t in discovery}
    assert {
        "draft_text",
        "build_keyboard",
        "read_updates",
        "request_maintenance",
        "inspect_metrics",
        "list_media",
    } <= names
    assert all(t["inputSchema"]["type"] == "object" for t in discovery)
    assert not any("approve" in name for name in names)
    r = rpc(
        client,
        h,
        "tools/call",
        {
            "name": "draft_text",
            "arguments": {
                "chat_id": "@test_channel",
                "text": "fixture",
                "idempotency_key": "mcp-draft-fixture",
            },
        },
    )
    assert r.status_code == 200
    assert r.json()["result"]["structuredContent"]["status"] == "draft"
    r = rpc(client, h, "tools/call", {"name": "list_operations", "arguments": {"limit": 1}})
    assert r.json()["result"]["structuredContent"]["untrusted_content"] is True
