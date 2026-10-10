import importlib.util
import json
import logging
import subprocess
from pathlib import Path

import httpx
import pytest

from tac import doctor

spec = importlib.util.spec_from_file_location("host_doctor", Path("scripts/doctor.py"))
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


def test_failure_redacts_entire_exception_and_continues():
    report = doctor.Report()

    def fail():
        raise RuntimeError("postgres://user:password@host bot123456:secret tac_private")

    report.check("one", fail, "Safe hint")
    report.check("two", lambda: ("PASS", "ok"), "")
    assert [x["status"] for x in report.checks] == ["FAIL", "PASS"]
    assert "password" not in json.dumps(report.checks)
    assert "tac_private" not in json.dumps(report.checks)


@pytest.mark.parametrize(
    "value",
    [
        "https://user:secret@example.com",
        "https://example.com/?token=x",
        "file:///etc/passwd",
        "https://example.com/path",
    ],
)
def test_public_origin_rejects_credentials_and_paths(value):
    with pytest.raises(ValueError):
        doctor.origin(value)


@pytest.mark.parametrize(
    "statuses,code", [(["PASS"], 0), (["WARN"], 2), (["SKIP"], 2), (["WARN", "FAIL"], 1)]
)
def test_exit_codes_do_not_hide_skips(statuses, code):
    report = {"checks": [{"status": s} for s in statuses]}
    assert host.summarize(report) == code


def test_real_mcp_discovery_and_readonly_call(client, agent, monkeypatch):
    # Real ASGI auth and MCP protocol; shared REST transport replaced by a fixture response.
    import tac.mcp_server as server

    seen = []

    def call(verb, path, *args, **kwargs):
        seen.append((verb, path))
        return {"version": "0.4.0", "role": "agent"}

    monkeypatch.setattr(server, "call", call)
    assert doctor.mcp_check(client, agent["Authorization"][7:])[0] == "PASS"
    assert seen == [("GET", "/v1/system")]


def test_mcp_business_error_cannot_be_reported_as_success(client, agent, monkeypatch):
    import tac.mcp_server as server

    monkeypatch.setattr(
        server, "call", lambda *a, **k: {"ok": False, "error": {"code": "gateway_unavailable"}}
    )
    with pytest.raises(ValueError):
        doctor.mcp_check(client, agent["Authorization"][7:])


def test_approval_probe_denied_without_mutating_operations(client, agent):
    from tac.db import Session, Operation
    from sqlalchemy import select, func

    response = client.post("/v1/operations/" + "0" * 32 + "/approve", headers=agent, json={})
    assert response.status_code == 403
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Operation)) == 0


def test_full_probe_is_bounded_readonly_and_ignores_response_secrets(monkeypatch, tmp_path):
    from tac.config import settings

    cfg = settings().model_copy(
        update={
            "storage_dir": tmp_path,
            "public_url": "https://test.example",
            "oauth_issuer": "",
            "allowed_chats": "@test_channel",
            "legacy_agent_keys_enabled": False,
        }
    )
    monkeypatch.setattr(doctor, "settings", lambda: cfg)
    requests = []
    real_client = httpx.Client

    def handler(request):
        requests.append((request.method, request.url.path))
        path = request.url.path
        if path.startswith("/bot"):
            result = {
                "getMe": {"id": 123, "is_bot": True},
                "getChatMember": {"status": "administrator", "can_post_messages": True},
                "getChat": {"type": "channel"},
            }[path.rsplit("/", 1)[-1]]
            return httpx.Response(200, json={"ok": True, "result": result})
        if path == "/health/ready":
            return httpx.Response(200, json={"status": "ready"})
        if path == "/mcp/":
            return httpx.Response(403 if "authorization" in request.headers else 401, json={})
        if "authorization" not in request.headers:
            return httpx.Response(401, json={})
        if path == "/v1/system":
            return httpx.Response(
                200,
                json={
                    "role": "owner",
                    "version": doctor.__version__,
                    "operations": {"uncertain": 1},
                    "paused": {"enabled": True},
                    "secret": "never-report-me",
                },
            )
        if path == "/v1/metrics":
            return httpx.Response(200, json={"worker_heartbeat_age_seconds": 1})
        raise AssertionError(path)

    monkeypatch.setattr(
        doctor.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )
    previous_logging = logging.root.manager.disable
    try:
        report = doctor.run()
    finally:
        logging.disable(previous_logging)
    by_name = {c["name"]: c for c in report["checks"]}
    assert by_name["queue"]["status"] == "WARN"
    assert by_name["worker"]["status"] == "PASS"
    assert by_name["telegram.destination.1"]["status"] == "PASS"
    assert by_name["mcp.protocol"]["status"] == "SKIP"
    assert "never-report-me" not in json.dumps(report)
    assert not any("operations" in path for _, path in requests)
    assert all(
        path.rsplit("/", 1)[-1] in {"getMe", "getChatMember", "getChat"}
        for _, path in requests
        if path.startswith("/bot")
    )


def test_host_timeout_reports_failure_without_raw_output(monkeypatch, tmp_path):
    monkeypatch.setattr(host, "ROOT", tmp_path)

    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired(["redacted"], 20, output="credential-not-for-report")

    monkeypatch.setattr(host, "command", fail)
    report = host.collect()
    assert host.summarize(report) == 1
    assert "credential-not-for-report" not in json.dumps(report)
    assert any(c["name"] == "application.probes" for c in report["checks"])
