from datetime import timedelta
import importlib.util
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from tac.config import settings
from tac.db import now
from tac.passwords import hash_password, verify_password
from tac.connections import OAuthClientInput, client_representation
from test_mcp import rpc


@pytest.fixture
def password_login(monkeypatch):
    monkeypatch.setattr(settings(), "owner_username", "test-owner")
    monkeypatch.setattr(settings(), "owner_password_hash", SecretStr(hash_password("test-password-long")))
    return {"username": "test-owner", "password": "test-password-long"}


def test_session_owner_csrf_logout_and_mcp_boundary(client, password_login):
    response = client.post("/v1/session", json=password_login)
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    csrf = {"X-CSRF-Token": response.json()["csrf"]}
    assert client.get("/v1/system").json()["role"] == "owner"
    assert client.get("/v1/session").json()["csrf"] == csrf["X-CSRF-Token"]
    assert client.post("/v1/system/pause?enabled=true").status_code == 403
    assert (
        client.post(
            "/v1/system/pause?enabled=true", headers={**csrf, "Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert client.post("/v1/system/pause?enabled=true", headers=csrf).status_code == 200
    # Session cookies are only a human console credential, not an MCP agent token.
    assert rpc(client, {}, "tools/list").status_code == 401
    assert client.delete("/v1/session", headers=csrf).status_code == 200
    assert client.get("/v1/system").status_code == 401


def test_session_revoked_by_password_change(client, password_login, monkeypatch):
    client.post("/v1/session", json=password_login)
    monkeypatch.setattr(settings(), "owner_password_hash", SecretStr(hash_password("replacement-password")))
    assert client.get("/v1/session").status_code == 401


def test_cross_site_login_and_invalid_password(client, password_login):
    assert (
        client.post("/v1/session", json=password_login, headers={"Origin": "https://evil.test"}).status_code
        == 403
    )
    assert client.post("/v1/session", json={**password_login, "password": "wrong"}).status_code == 401
    assert client.get("/v1/system").status_code == 401


def test_login_rate_limit_before_hashing(client, password_login, monkeypatch):
    monkeypatch.setattr("tac.web_auth.verify_password", lambda *args: False)
    for _ in range(30):
        assert client.post("/v1/session", json=password_login).status_code == 401
    assert client.post("/v1/session", json=password_login).status_code == 429


def test_api_and_mcp_scoped_key_independent_of_oauth(client, password_login):
    csrf = client.post("/v1/session", json=password_login).json()["csrf"]
    response = client.post(
        "/v1/agents",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "API assistant",
            "preset": "READ",
            "chats": ["@test_channel"],
            "expires_at": (now() + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 201
    token = response.json()["credential"]
    headers = {"Authorization": "Bearer " + token}
    # Explicit Bearer identity wins even in an owner browser session.
    assert client.get("/v1/connections", headers=headers).status_code == 403
    assert (
        client.post(
            "/v1/connections/oauth-clients",
            json={"name": "x", "redirect_uri": "https://ai.test/callback"},
            headers=headers,
        ).status_code
        == 403
    )
    assert client.get("/v1/system", headers=headers).json()["role"] != "owner"
    assert rpc(client, headers, "tools/list").status_code == 200
    assert client.get("/agent-guide").status_code == 200
    assert token not in client.get("/v1/connections").text
    assert token not in client.get("/openapi.json").text


@pytest.mark.parametrize(
    "uri",
    [
        "http://ai.test/callback",
        "https://ai.test/*",
        "https://user:pass@ai.test/cb",
        "https://ai.test/cb#x",
        "https://ai.test/\ncb",
    ],
)
def test_oauth_rejects_unsafe_callback(uri):
    with pytest.raises(ValueError):
        OAuthClientInput(name="Example", redirect_uri=uri)


def test_client_uses_code_pkce_audience_scope_without_password_grant():
    c = client_representation(
        OAuthClientInput(name="AI", redirect_uri="https://ai.test/callback"), "test-client"
    )
    assert c["redirectUris"] == ["https://ai.test/callback"]
    assert not c["directAccessGrantsEnabled"] and not c["implicitFlowEnabled"]
    assert not c["serviceAccountsEnabled"] and not c["publicClient"]
    assert c["attributes"]["pkce.code.challenge.method"] == "S256"
    assert "system:read" in c["defaultClientScopes"] and "tac-agent" in c["defaultClientScopes"]


def test_web_creates_provider_client_without_leaking_admin_secret(client, owner, monkeypatch):
    monkeypatch.setattr(settings(), "oauth_issuer", "https://id.test/auth/realms/test")
    monkeypatch.setattr(settings(), "oauth_admin_client_secret", SecretStr("test-admin-secret"))
    requests = []

    def respond(r):
        requests.append(r)
        if r.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "admin-access"})
        if r.url.path.endswith("/client-secret"):
            return httpx.Response(200, json={"value": "new-client-secret"})
        if r.method == "POST":
            return httpx.Response(201)
        return httpx.Response(200, json=[{"id": "provider-id", "clientId": r.url.params["clientId"]}])

    original = httpx.Client
    monkeypatch.setattr(
        "tac.connections.httpx.Client",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(respond)),
    )
    r = client.post(
        "/v1/connections/oauth-clients",
        headers=owner,
        json={"name": "AI", "redirect_uri": "https://ai.test/cb"},
    )
    assert r.status_code == 201
    assert r.json()["client_secret"] == "new-client-secret"
    assert "test-admin-secret" not in r.text and "admin-access" not in r.text
    assert len(requests) == 4


def test_password_hash_and_upgrade_config_adoption():
    hashed = hash_password("correct-password")
    assert verify_password("correct-password", hashed)
    assert not verify_password("incorrect-password", hashed)
    assert not verify_password("correct-password", "invalid")
    path = Path(__file__).resolve().parents[1] / "scripts/upgrade.py"
    spec = importlib.util.spec_from_file_location("upgrade", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.managed_change(".dockerignore", ".env\ndata\n", ".env\ndata\n.oauth*.env\ndata/\n")
    assert not module.managed_change(".dockerignore", ".env\ndata\n", "data\n")
    assert not module.managed_change("tac/api.py", "old", "new")


def test_cloud_plugin_bundle_has_registered_mapping_not_desktop_mcp():
    import io
    import json
    import zipfile
    from tac.plugin_package import build_package

    app_id = "asdk_app_" + "a" * 32
    with zipfile.ZipFile(
        io.BytesIO(build_package("https://tac.example.test", "plugin_" + app_id))
    ) as archive:
        assert "telegram-control/mcp.json" not in archive.namelist()
        assert "telegram-control/.mcp.json" not in archive.namelist()
        mapping = json.loads(archive.read("telegram-control/.app.json"))
        assert mapping["apps"]["telegram-control"]["id"] == app_id
        manifest = json.loads(archive.read("telegram-control/plugin.json"))
        assert manifest["extensions"]["com.openai"]["apps"] == "./.app.json"
    with pytest.raises(ValueError):
        build_package("https://tac.example.test", "plugins_some_zip")
    with pytest.raises(ValueError):
        build_package("https://user:secret@tac.example.test")


def test_invalid_explicit_auth_never_falls_back_to_owner_cookie(client, password_login):
    client.post("/v1/session", json=password_login)
    assert client.get("/v1/system", headers={"Authorization": "Basic invalid"}).status_code == 401


def test_initial_oauth_setup_does_not_revive_existing_revoked_grant(client, owner, monkeypatch):
    from test_governance import grant
    from tac.db import Session, AgentGrant
    from tac.access_setup import ensure_grant

    g, _ = grant(client, owner, oauth_subject="existing-owner")
    with Session.begin() as db:
        db.get(AgentGrant, g["id"]).revoked_at = now()
    monkeypatch.setattr(settings(), "owner_oauth_subject", "existing-owner")

    def unexpected(*args, **kwargs):
        raise AssertionError("Setup must not create/renew an existing revoked grant")

    monkeypatch.setattr("tac.access_setup.httpx.Client", unexpected)
    ensure_grant()
    with Session() as db:
        assert db.get(AgentGrant, g["id"]).revoked_at is not None
