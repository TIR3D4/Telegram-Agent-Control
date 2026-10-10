"""Docker Compose installation smoke: no real bot credentials or external sends."""

import json
import secrets
import subprocess
import time
from pathlib import Path
import httpx

password = secrets.token_urlsafe(32)
owner = secrets.token_urlsafe(40)
values = {
    "TAC_DB_PASSWORD": password,
    "TAC_DATABASE_URL": f"postgresql+psycopg://tac:{password}@postgres:5432/tac",
    "TAC_STORAGE_DIR": "/data/media",
    "TAC_OWNER_KEY": owner,
    "TAC_AGENT_KEY": secrets.token_urlsafe(40),
    "TAC_READER_KEY": secrets.token_urlsafe(40),
    "TAC_ALLOWED_CHATS": "@ci_test",
    "TAC_BOT_TOKEN": "",
    "TAC_PORT": "8787",
}
Path(".env").write_text("\n".join(k + "=" + json.dumps(v) for k, v in values.items()) + "\n")


def ready(client):
    for attempt in range(45):
        try:
            response = client.get("/v1/system")
            if response.status_code == 200 and response.json().get("worker"):
                assert response.json()["methods"] == 185
                return response.json()
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError("Compose not ready")


try:
    subprocess.run(["docker", "compose", "up", "-d", "--build"], check=True)
    with httpx.Client(
        base_url="http://127.0.0.1:8787",
        trust_env=False,
        timeout=15,
        headers={"Authorization": "Bearer " + owner},
    ) as c:
        ready(c)
        diagnosis = subprocess.run(
            ["./scripts/tacctl", "doctor", "--no-telegram", "--json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        report = json.loads(diagnosis.stdout)
        print(json.dumps(report), flush=True)
        assert diagnosis.returncode == 2, report
        assert report["summary"]["FAIL"] == 0, report
        assert any(
            item["name"] == "database.migrations" and item["status"] == "PASS" for item in report["checks"]
        )
        assert any(item["name"] == "public.mcp" and item["status"] == "PASS" for item in report["checks"])
        assert any(item["name"] == "mcp.protocol" and item["status"] == "PASS" for item in report["checks"])
        assert any(
            item["name"] == "approval.agent_boundary" and item["status"] == "PASS"
            for item in report["checks"]
        )
        print("Doctor Compose and authenticated MCP probes passed; live Telegram explicitly skipped")
        assistant_config = c.put(
            "/v1/assistant/config",
            json={
                "provider": "openai",
                "model": "ci-mock-model",
                "api_key": "sk-ci-fake-never-a-live-key-12345",
                "channels": ["@ci_test"],
            },
        )
        assistant_config.raise_for_status()
        grant_id = assistant_config.json()["grant_id"]
        assert "sk-ci-fake" not in assistant_config.text
        content = b"Backup and restore fixture; not sent to Telegram."
        response = c.post("/v1/assets", files={"file": ("fixture.txt", content, "text/plain")})
        response.raise_for_status()
        asset_id = response.json()["id"]
        response = c.post(
            "/v1/operations",
            json={
                "method": "sendDocument",
                "payload": {"chat_id": "@ci_test", "document": "attach://document"},
                "attachments": {"document": asset_id},
                "idempotency_key": "ci-lifecycle-document",
            },
        )
        response.raise_for_status()
        operation = response.json()
        assert operation["status"] == "draft"
        subprocess.run(["./scripts/tacctl", "backup"], check=True)
        backup = sorted(Path("backups").iterdir())[-1]
        subprocess.run(["./scripts/tacctl", "verify-backup", str(backup)], check=True)
        ready(c)
        c.post("/v1/operations/" + operation["id"] + "/cancel").raise_for_status()
        subprocess.run(["./scripts/tacctl", "restore", str(backup)], input="RESTORE\n", text=True, check=True)
        assert ready(c)["paused"]["enabled"] is True
        assert c.get("/v1/operations/" + operation["id"]).json()["status"] == "draft"
        assert c.get("/v1/assets/" + asset_id).content == content
        assert c.get("/v1/assistant/config").json()["grant_id"] == grant_id
        subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "api",
                "python",
                "-c",
                "from tac.assistant import config,unlock; assert unlock(config()['provider_secret']) == 'sk-ci-fake-never-a-live-key-12345'",
            ],
            check=True,
        )
        subprocess.run(["./scripts/tacctl", "uninstall"], check=True)
        subprocess.run(["./scripts/tacctl", "start"], check=True)
        assert ready(c)["paused"]["enabled"] is True
        assert c.get("/v1/assets/" + asset_id).content == content
        subprocess.run(
            ["./scripts/tacctl", "rollback", str(backup)], input="ROLLBACK\n", text=True, check=True
        )
        assert ready(c)["paused"]["enabled"] is True
        assert c.get("/v1/assets/" + asset_id).content == content
        print(
            "Compose readiness, verified backup/restore, same-revision rollback and data-preserving uninstall/reinstall passed"
        )

finally:
    subprocess.run(["docker", "compose", "down", "-v"])
    Path(".env").unlink(missing_ok=True)
