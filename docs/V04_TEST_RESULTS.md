# v0.4 validation — 2026-10-10

## Executed locally

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **515 passed, 4 skipped**, 17.16 s; SQLite and mocked Telegram/provider boundaries |
| `.venv/bin/ruff check tac scripts tests` | Passed |
| `.venv/bin/ruff format --check tac scripts tests` | 56 files formatted |
| `.venv/bin/mypy --follow-imports=silent --ignore-missing-imports tac/gateway.py tac/oauth.py tac/security.py tac/body_limit.py tac/observability.py` | Passed, 5 files |
| `.venv/bin/bandit -q -r tac scripts -ll` | Passed |
| `node --check tac/static/workspace.js` | Passed |
| `node --test integrations/chatgpt-cloud/tests/connector.test.mjs` | **18 passed**, mocked gateway; includes real byte encoding and boundary checks |
| `npm test -- --project=chromium` | **10 passed**, 11.6 s; actual local HTTP/MCP and browser interaction |
| `git diff --check` | Passed |

Browser coverage: password login/session/logout, granted identity precedence, real MCP initialization/discovery, owner-token rejection, photo upload and attachment binding, URL buttons, explicit schedule, saved-operation reuse, independent owner approval, agent denial, existing advanced API/emoji/log/maintenance navigation, private key cleanup, 390×844 layout and optional legacy chat.

These tests do not send messages to Telegram. Connector tests use a mock upstream; local browser MCP calls exercise the actual SDK transport and authenticated local REST server.

## Observed live

Existing private ChatGPT plugin `inspect_system` returned version **0.3.0**, an agent identity, a configured bot, a fresh worker heartbeat and execution unpaused. This verifies the pre-upgrade read-only plugin path. It does not prove v0.4 is installed on the VPS. No new live Telegram write was submitted.

## Blocked / not verified

- WebKit iPhone-profile tests: browser could not launch because system libraries are missing. `npx playwright install-deps webkit` failed on environment permissions (`setgroups` / apt). Chromium mobile viewport is **not** physical iPhone Safari evidence.
- Docker/Compose build and full VPS upgrade: Docker is unavailable in this execution environment; no scoped remote deployment executor is exposed.
- PostgreSQL-specific concurrent-worker cases were skipped locally. The existing CI PostgreSQL job is retained; inspect its exact revision result before deployment.
- Codex and Claude host setup/invocation: generated config is parsed/validated against official documented shapes; no signed-in client was connected during this run.
- Cloud adapter release and VPS release are separate. See implementation report for deployment outcome; tests alone are not deployment evidence.

No database model or migration revision changed. Existing migration/backup/upgrade behavior tests remain in the full suite. No database downgrade or restore was run on production.

## Private adapter build and live deployment

In the existing Site source checkout: `node --test tests/connector.test.mjs tests/edge-runtime.mjs` — **19 passed**, including actual workerd with mocked external transport. `npx tsc --noEmit` and native Site production build passed. The owner-private deployment completed successfully. A subsequent real plugin `inspect_system` call confirmed continuity of the stored grant and gateway connection; production VPS still reports v0.3. New tool invocation has not been observed because host discovery in this conversation has not refreshed.

A direct SSH connection probe failed with `Network is unreachable`; no upgrade command was executed on the VPS.
