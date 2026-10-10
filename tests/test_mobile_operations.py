"""Operator lifecycle and provider HTTP boundary tests; no production credentials."""

import asyncio
import importlib.util
import json
import tarfile
import io
from pathlib import Path
import httpx
import pytest
from tac import assistant
from test_assistant import configure

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_vault_is_verified_backup_member(tmp_path, monkeypatch):
    m = module("backup_manifest")
    d = tmp_path / "backup"
    d.mkdir()
    (d / "database.dump").write_bytes(b"test-fixture")
    with tarfile.open(d / "media.tar.gz", "w:gz") as t:
        info = tarfile.TarInfo("./.assistant-vault")
        info.mode = 0o600
        info.size = 44
        t.addfile(info, io.BytesIO(b"x" * 44))
    monkeypatch.setattr(m.subprocess, "check_output", lambda *a, **kw: "a" * 40)
    assert m.create(d)["commit"] == "a" * 40
    with tarfile.open(d / "media.tar.gz", "w:gz") as t:
        info = tarfile.TarInfo("./.assistant-vault")
        info.mode = 0o644
        info.size = 44
        t.addfile(info, io.BytesIO(b"x" * 44))
    with pytest.raises(ValueError, match="Unsafe assistant vault"):
        m.create(d)


def test_upgrade_failure_report_is_private_and_has_commit(tmp_path):
    m = module("upgrade")
    m.REPORT_PATH = tmp_path / "report.json"
    m.REPORT.update(
        status="failed", target_commit="a" * 40, step="docker compose run", error_type="CalledProcessError"
    )
    m.save_report()
    assert json.loads(m.REPORT_PATH.read_text())["status"] == "failed"
    assert m.REPORT_PATH.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("provider", list(assistant.PROVIDERS))
def test_provider_http_auth_and_bounded_schema(client, owner, monkeypatch, provider):
    c = configure(client, owner)
    c["provider"] = provider
    original = httpx.AsyncClient
    captured = []

    def handler(request):
        captured.append(request)
        body = json.loads(request.content)
        assert request.url == assistant.PROVIDERS[provider]
        assert "agent_secret" not in json.dumps(body) and "provider_secret" not in json.dumps(body)
        assert body["parallel_tool_calls"] is False
        assert body["max_completion_tokens"] == 1500
        assert request.headers["authorization"].startswith("Bearer sk-mock")
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "سلام"}}]})

    monkeypatch.setattr(
        assistant.httpx, "AsyncClient", lambda **kw: original(**kw, transport=httpx.MockTransport(handler))
    )
    assert asyncio.run(assistant.completion(c, [{"role": "user", "content": "test"}]))["choices"]
    assert len(captured) == 1


def test_provider_failure_does_not_leak_response_or_retry(client, owner, monkeypatch):
    c = configure(client, owner)
    original = httpx.AsyncClient
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": assistant.unlock(c["provider_secret"])})

    monkeypatch.setattr(
        assistant.httpx, "AsyncClient", lambda **kw: original(**kw, transport=httpx.MockTransport(handler))
    )
    with pytest.raises(Exception) as error:
        asyncio.run(assistant.completion(c, []))
    assert assistant.unlock(c["provider_secret"]) not in str(error.value)
    assert len(calls) == 1


def test_connection_test_is_readonly_and_agent_cannot_call(client, owner, agent):
    configure(client, owner)
    assert client.post("/v1/assistant/connection-test", headers=agent).status_code == 403
    o = client.post("/v1/assistant/connection-test", headers=owner).json()
    assert o["method"] == "getMe" and o["status"] == "queued"
    assert o["approved_by"] is None


def test_upgrade_from_previous_schema_and_roundtrip(tmp_path):
    import os
    import subprocess
    import sys

    env = {**os.environ, "TAC_DATABASE_URL": "sqlite:///" + str(tmp_path / "migration.sqlite")}
    for command in [
        ["alembic", "upgrade", "9906fa12eb62"],
        ["tac.maintenance", "pause-upgrade"],
        ["alembic", "upgrade", "head"],
        ["alembic", "check"],
        ["alembic", "downgrade", "9906fa12eb62"],
        ["alembic", "upgrade", "head"],
    ]:
        result = subprocess.run(
            [sys.executable, "-m", *command], cwd=ROOT, env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_cross_revision_db_rollback_is_blocked(monkeypatch):
    import sys

    backup = module("backup_manifest")
    monkeypatch.setitem(sys.modules, "backup_manifest", backup)
    m = module("rollback")
    monkeypatch.setattr(m, "verify", lambda d: {"commit": "a" * 40})
    monkeypatch.setattr(
        m.subprocess, "check_output", lambda args, **kw: b"" if "status" in args else "b" * 40
    )
    monkeypatch.setattr(sys, "argv", ["rollback.py", "/not-a-real-production-backup"])
    with pytest.raises(SystemExit, match="Cross-revision database rollback is blocked"):
        m.main()


def test_postgres_chat_claim_is_not_replayed(client, owner, monkeypatch):
    import concurrent.futures
    import threading
    from tac.db import engine

    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock verification runs in CI")
    configure(client, owner)
    client.post(
        "/v1/assistant/turns", headers=owner, json={"text": "hello", "idempotency_key": "pg-chat-claim"}
    )
    entered = threading.Event()
    release = threading.Event()
    calls = []

    async def complete(c, m):
        calls.append(1)
        entered.set()
        release.wait(5)
        return {"choices": [{"message": {"role": "assistant", "content": "done"}}]}

    monkeypatch.setattr(assistant, "completion", complete)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(lambda: asyncio.run(assistant.cycle()))
        assert entered.wait(5)
        try:
            assert not asyncio.run(assistant.cycle())
        finally:
            release.set()
        assert future.result(timeout=5)
    assert len(calls) == 1
