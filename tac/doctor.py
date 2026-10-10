"""Read-only operator diagnostics; no enqueue, approval or publication."""

import json
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from tac import __version__
from tac.config import settings
from tac.db import engine
from tac.telegram import Telegram, TelegramError


class Report:
    def __init__(self):
        self.checks = []

    def add(self, name, status, message, hint=""):
        self.checks.append(dict(name=name, status=status, message=message, hint=hint))

    def check(self, name, action, hint):
        start = time.monotonic()
        try:
            status, message = action()
            self.add(name, status, message, hint if status != "PASS" else "")
        except Exception as exc:
            # Exceptions may contain bot URLs or database passwords. Never echo them.
            code = "Check failed"
            if isinstance(exc, httpx.TimeoutException):
                code = "Network timeout"
            elif isinstance(exc, httpx.HTTPStatusError):
                code = f"HTTP {int(exc.response.status_code)}"
            elif isinstance(exc, TelegramError) and isinstance(exc.code, int):
                code = f"Telegram error {exc.code}"
            self.add(name, "FAIL", code + "; raw error omitted to protect credentials.", hint)
        self.checks[-1]["duration_ms"] = round((time.monotonic() - start) * 1000)


def verdict(ok, good, bad):
    return ("PASS", good) if ok else ("FAIL", bad)


def origin(value):
    p = urlsplit(value)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("Invalid origin")
    if p.path not in {"", "/"} or p.query or p.fragment:
        raise ValueError("Invalid origin")
    return value.rstrip("/")


def mcp_check(client, token):
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}

    def rpc(method, params, ident):
        response = client.post(
            "/mcp/", headers=headers, json={"jsonrpc": "2.0", "id": ident, "method": method, "params": params}
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error") or data.get("id") != ident or "result" not in data:
            raise ValueError("Invalid MCP response")
        return data["result"]

    info = rpc(
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "tac-doctor", "version": "1"},
        },
        1,
    )
    headers["MCP-Protocol-Version"] = info["protocolVersion"]
    response = client.post(
        "/mcp/", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
    )
    response.raise_for_status()
    discovery = rpc("tools/list", {}, 2)
    if not any(t.get("name") == "inspect_system" for t in discovery["tools"]):
        raise ValueError("Missing tool")
    result = rpc("tools/call", {"name": "inspect_system", "arguments": {}}, 3)
    content = result.get("structuredContent")
    if content is None:
        blocks = result.get("content", [])
        content = json.loads(next(block["text"] for block in blocks if block.get("type") == "text"))
    if (
        result.get("isError")
        or not isinstance(content, dict)
        or not content.get("version")
        or content.get("role") not in {"agent", "reader"}
    ):
        raise ValueError("Tool failed or returned an unexpected identity")
    return "PASS", "MCP initialize, discovery and read-only inspect_system succeeded."


def run(agent_token="", telegram=True):
    logging.disable(logging.CRITICAL)
    r = Report()
    cfg = settings()
    r.add("version", "PASS", "Running application " + __version__)

    def config():
        cfg.check()
        return "PASS", "Configuration validation passed."

    r.check("configuration", config, "Review key lengths and OAuth configuration locally; never share .env.")

    def database():
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            current = set(MigrationContext.configure(conn).get_current_heads())
        expected = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
        return verdict(
            current == expected,
            "Database reachable; migration matches application head.",
            "Migration revision mismatch.",
        )

    r.check(
        "database.migrations",
        database,
        "Use the backed-up upgrade workflow; do not blindly downgrade the database.",
    )

    def storage():
        free = shutil.disk_usage(cfg.storage_dir).free
        return "PASS" if free >= 1024**3 else "WARN", f"Media filesystem free: {free // 1024**2} MiB."

    r.check("storage", storage, "Review volume space and media retention.")
    with httpx.Client(
        base_url="http://127.0.0.1:8787", timeout=10, trust_env=False, follow_redirects=False
    ) as local:
        owner = {"Authorization": "Bearer " + cfg.owner_key.get_secret_value()}

        def get(path):
            response = local.get(path, headers=owner)
            response.raise_for_status()
            return response.json()

        def ready():
            response = local.get("/health/ready")
            return verdict(
                response.status_code == 200 and response.json().get("status") == "ready",
                "Local readiness passed.",
                "Local API not ready.",
            )

        r.check("rest.readiness", ready, "Inspect API and database service status.")

        def identity():
            data = get("/v1/system")
            return verdict(
                data.get("version") == __version__ and data.get("role") == "owner",
                "Authenticated REST matches installed version.",
                "REST identity or image version mismatch.",
            )

        r.check("rest.identity", identity, "Check owner configuration and selected application image.")

        def worker():
            age = get("/v1/metrics").get("worker_heartbeat_age_seconds")
            return verdict(
                isinstance(age, (float, int)) and 0 <= age < cfg.worker_stale_seconds,
                "Worker heartbeat fresh.",
                "Worker heartbeat missing, stale or in the future.",
            )

        r.check("worker", worker, "Inspect worker status, database access and server clock.")

        def queue():
            data = get("/v1/system")
            counts = data["operations"]
            paused = data.get("paused", {}).get("enabled", False)
            warning = paused or counts.get("uncertain", 0) or counts.get("failed", 0)
            summary = ", ".join(
                f"{key}={int(counts.get(key, 0))}"
                for key in ("draft", "queued", "running", "failed", "uncertain")
            )
            return "WARN" if warning else "PASS", f"Execution paused={bool(paused)}; {summary}."

        r.check(
            "queue", queue, "Review operations before resuming. Never blindly resend uncertain deliveries."
        )
        r.check(
            "rest.authentication",
            lambda: verdict(
                local.get("/v1/system").status_code == 401,
                "Anonymous REST denied.",
                "Anonymous REST not denied as expected.",
            ),
            "Inspect authentication middleware.",
        )
        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        r.check(
            "mcp.authentication",
            lambda: verdict(
                local.post("/mcp/", json=payload).status_code == 401,
                "Anonymous MCP denied.",
                "Anonymous MCP not denied as expected.",
            ),
            "Inspect MCP route and authentication.",
        )
        r.check(
            "mcp.owner_boundary",
            lambda: verdict(
                local.post("/mcp/", json=payload, headers=owner).status_code == 403,
                "Owner credential rejected by MCP.",
                "MCP owner boundary did not return 403.",
            ),
            "Never give owner credentials to agents.",
        )
        token = agent_token or (cfg.reader_key.get_secret_value() if cfg.legacy_agent_keys_enabled else "")
        if token:
            r.check(
                "mcp.protocol",
                lambda: mcp_check(local, token),
                "Use an unexpired scoped credential with system:read; check quota and MCP logs.",
            )
            # Missing resource prevents mutation even if authorization regresses.
            r.check(
                "approval.agent_boundary",
                lambda: verdict(
                    local.post(
                        "/v1/operations/" + "0" * 32 + "/approve",
                        headers={"Authorization": "Bearer " + token},
                        json={},
                    ).status_code
                    == 403,
                    "Agent denied owner approval route.",
                    "Approval route did not deny agent before resource access.",
                ),
                "Review owner authorization dependency before allowing agent operations.",
            )
        else:
            r.add(
                "mcp.protocol",
                "SKIP",
                "No scoped diagnostic credential supplied.",
                "Run doctor --agent for a hidden scoped credential prompt.",
            )
            r.add("approval.agent_boundary", "SKIP", "Requires scoped diagnostic credential.")

    def public():
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as c:
            response = c.get(origin(cfg.public_url) + "/health/ready")
            response.raise_for_status()
            return verdict(
                response.json().get("status") == "ready",
                "Public URL reachable from server; TLS verified for HTTPS.",
                "Public readiness invalid.",
            )

    r.check(
        "public.readiness",
        public,
        "Check DNS, TLS, proxy and firewall. Server reachability does not prove client connectivity.",
    )

    def public_mcp():
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as c:
            response = c.post(
                origin(cfg.public_url) + "/mcp/",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
            return verdict(
                response.status_code == 401,
                "Public MCP POST route reachable and requires authentication.",
                "Public MCP did not return expected 401; check proxy/routing.",
            )

    r.check(
        "public.mcp",
        public_mcp,
        "Verify /mcp/ is forwarded without redirects or 405 responses; no credentials are sent to public probes.",
    )
    if cfg.oauth_issuer:

        def oauth():
            with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as c:
                resource = c.get(origin(cfg.public_url) + "/.well-known/oauth-protected-resource")
                resource.raise_for_status()
                issuer = cfg.oauth_issuer.rstrip("/")
                response = c.get(issuer + "/.well-known/openid-configuration")
                response.raise_for_status()
                return verdict(
                    cfg.oauth_issuer in resource.json().get("authorization_servers", [])
                    and response.json().get("issuer", "").rstrip("/") == issuer,
                    "OAuth resource and issuer discovery agree.",
                    "OAuth discovery mismatch.",
                )

        r.check(
            "oauth.discovery",
            oauth,
            "Review issuer metadata and proxy routes; browser login is a separate test.",
        )
    else:
        r.add("oauth.discovery", "SKIP", "OAuth not configured; bearer mode may still work.")
    if telegram and cfg.bot_token.get_secret_value():
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as c:
            tg = Telegram(c)
            bot = {}

            def bot_identity():
                bot.update(tg.call("getMe", {}))
                return verdict(
                    bot.get("is_bot") is True, "Telegram getMe succeeded.", "Unexpected Telegram identity."
                )

            r.check("telegram.identity", bot_identity, "Verify bot credential and outgoing HTTPS locally.")
            chats = sorted(cfg.chats)
            if len(chats) > 10:
                r.add(
                    "telegram.channel_limit", "WARN", "Only first 10 destinations checked to bound runtime."
                )
            if not chats:
                r.add("telegram.destinations", "WARN", "No allowed destinations configured.")
            for index, chat in enumerate(chats[:10], 1):

                def permission(chat=chat):
                    member = tg.call("getChatMember", {"chat_id": chat, "user_id": bot["id"]})
                    info = tg.call("getChat", {"chat_id": chat})
                    if info.get("type") != "channel":
                        return (
                            "WARN",
                            "Non-channel destination; posting rights require context-specific validation.",
                        )
                    return verdict(
                        member.get("status") == "creator"
                        or (
                            member.get("status") == "administrator"
                            and member.get("can_post_messages") is True
                        ),
                        "Channel posting permission confirmed; no message sent.",
                        "Bot lacks channel posting permission.",
                    )

                if bot.get("id"):
                    r.check(
                        f"telegram.destination.{index}",
                        permission,
                        "Review bot posting permissions for this configured destination.",
                    )
                else:
                    r.add(
                        f"telegram.destination.{index}", "SKIP", "getMe failed; permission check unavailable."
                    )
    else:
        r.add("telegram.identity", "SKIP", "Telegram probe disabled or bot not configured.")
    r.add(
        "client.end_to_end",
        "SKIP",
        "ChatGPT/Codex/Claude account connection and UI rendering need client-side verification.",
    )
    r.add(
        "delivery.end_to_end",
        "SKIP",
        "No message sent; publishing, scheduling delivery and recovery belong in isolated tests.",
    )
    return {"format": 1, "created_at": datetime.now(timezone.utc).isoformat(), "checks": r.checks}


if __name__ == "__main__":
    try:
        options = json.load(sys.stdin)
        result = run(options.get("credential", ""), options.get("telegram", True))
    except Exception:
        result = {
            "checks": [
                {
                    "name": "diagnostic.runtime",
                    "status": "FAIL",
                    "message": "Diagnostic runtime failed; details omitted to protect credentials.",
                    "hint": "Check application configuration and dependencies.",
                }
            ]
        }
    print(json.dumps(result))
