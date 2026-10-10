import json
import tomllib

import pytest
from pydantic import SecretStr
from tac.config import settings
from tac.connection_profiles import profiles


def test_client_configs_parse_and_never_embed_keys(client, owner, monkeypatch):
    monkeypatch.setattr(settings(), "public_url", "https://control.example.test")
    monkeypatch.setattr(settings(), "oauth_admin_client_secret", SecretStr("not-for-clients"))
    response = client.get("/v1/connections", headers=owner)
    assert response.status_code == 200
    assert "not-for-clients" not in response.text
    data = response.json()
    assert data["verification"] == "configuration_only"
    items = {p["id"]: p for p in data["profiles"]}
    assert set(items) == {"api", "mcp", "codex", "claude", "chatgpt"}
    codex = tomllib.loads(items["codex"]["config"])["mcp_servers"]["telegram_control"]
    assert codex["bearer_token_env_var"] == "TAC_TOKEN"
    assert codex["url"] == "https://control.example.test/mcp/"
    claude = json.loads(items["claude"]["config"])["mcpServers"]["telegram_control"]
    assert claude["headers"]["Authorization"] == "Bearer ${TAC_TOKEN}"
    assert claude["type"] == "http"
    assert data["approval_policy"] == "independent_owner"


def test_profiles_owner_only(client, agent):
    assert client.get("/v1/connections", headers=agent).status_code == 403
    assert client.get("/v1/connections").status_code == 401


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@example.test",
        "javascript:alert(1)",
        "https://example.test/other",
        "https://example.test?secret=value",
    ],
)
def test_reject_unsafe_config_origin(url):
    with pytest.raises(ValueError):
        profiles(url, False)
