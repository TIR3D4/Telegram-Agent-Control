# One-command installation diagnosis

From the installed checkout:

```bash
./scripts/tacctl doctor
```

The command inspects the running installation without publishing, approving, resuming, restarting, applying migrations or repairing anything. It makes read-only Telegram `getMe`, `getChatMember` and `getChat` requests by default. Existing quota/audit accounting may record authenticated probes. It does not run destructive integration tests against your production data.

Results are `PASS`, `WARN`, `FAIL`, or `SKIP`. Each problem includes a next action. An intentional execution pause is a warning, not a broken worker. A successful health URL alone never means every integration works.

| Check | Evidence |
|---|---|
| Checkout / app | Git commit, running package version, authenticated REST version match |
| Host | Disk space, reboot marker, secret-file permissions |
| Compose | Configuration validation, API/worker/Postgres status, observed proxy/OAuth services, migration container exit |
| Database | `SELECT 1`, current migration heads vs installed migration scripts |
| Worker / queue | Heartbeat age, paused state, failed/uncertain and outstanding operation counts |
| API / security | Readiness, authenticated identity, anonymous REST/MCP rejection, owner credential rejected by MCP |
| Public routing | Configured URL readiness and unauthenticated MCP POST requiring 401; HTTPS certificates verified |
| OAuth | Resource and issuer discovery agreement, when configured |
| Telegram | Bot identity and channel posting rights for up to 10 configured destinations; nothing sent |
| Backup | Latest local backup manifest checksums and safe archive structure; no restore |
| MCP with credential | Initialize, initialized notification, tools/list, actual read-only inspect_system tool call, agent rejected by owner approval route |

Private reports are saved in `diagnostics/TIMESTAMP.txt` and `.json`, with directory mode 0700 and file mode 0600. They exclude tokens, raw errors, environment values, raw logs, message content and channel identifiers. Reports and diagnostic output are excluded from Git and Docker build contexts. Share the report, not `.env` or console keys.

## Authenticated MCP test

If a legacy reader key is already configured and enabled it is used. Otherwise run:

```bash
./scripts/tacctl doctor --agent
```

Enter an **existing scoped agent credential** at the hidden prompt. It is passed to the container over stdin, never as a command argument, stored file or report. A READ grant with `system:read` is sufficient. Expired/revoked credentials and exhausted quota fail the check. Without a credential, authenticated MCP and agent approval-boundary checks explicitly say `SKIP`; no elevated temporary agent is created. The owner key is used only for local REST inspection and the negative owner-on-MCP test.

## Automation

```bash
./scripts/tacctl doctor --json
./scripts/tacctl doctor --no-telegram
```

Exit codes:

- `0`: all performed checks pass, no warnings/skips.
- `1`: at least one failure (other checks still run where possible).
- `2`: no failure, but warnings or unverified/skipped areas remain.

Do not chain upgrades or automatic remediation based only on exit code 2. Client-side and delivery tests are intentionally skipped by production diagnosis, so a normal healthy deployment can return 2. Network probes have 10-second request timeouts; the application group is capped at 420 seconds, backup verification at 60 seconds. Application-group timeout reports failure, not success.

## What this cannot prove

Server reachability does not prove ChatGPT/Codex/Claude account access, browser OAuth login, mobile rendering, actual publishing or future scheduled delivery. Those are labelled unverified. No command can prove the absence of all bugs. Regression, authorization, approval, scheduling, uncertain delivery, migrations, backup/restore and browser tests run in isolated CI, not against production. See [testing](TESTING.md) and [CI](https://github.com/TIR3D4/Telegram-Agent-Control/actions).

This diagnostic is a local operator command. It does not add shell execution or owner authority to agent tools. The live Telegram reads are direct local probes, not a worker delivery test. Telegram flooding, network failure or revoked bot access produces failure without exposing the upstream token-bearing URL.

## Verification of this change

Local commands on 2026-10-10:

- `PYTHONPATH=. .venv/bin/pytest -q`: **533 passed, 4 skipped** (PostgreSQL-only cases skipped locally).
- New diagnostic tests: **18 passed**, including real ASGI MCP initialization/discovery, a fixture-backed read-only tool call, actual agent approval denial, raw exception suppression and timeout reporting.
- `ruff check tac scripts tests`, `ruff format --check tac scripts tests`, `bandit -q -r tac scripts -ll`, `bash -n scripts/tacctl`: passed.
- Live Telegram calls in the new diagnostic tests are mocked. The production server has not yet run this new command. CI additionally runs doctor against the installed Compose stack with Telegram disabled, a generated test-only reader credential, real HTTP MCP discovery/tool execution and agent approval denial. It verifies that failures are zero while skipped coverage remains explicit. Container health `starting` is a warning; `unhealthy`, missing workers and failed migrations are failures.
