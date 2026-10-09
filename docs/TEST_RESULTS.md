# Test results — 2026-10-09

Evidence applies to the indicated revision/environment, not every possible deployment. No live Telegram sends, production credentials, external OAuth account linking or VPS deployment were performed.

## Full CI evidence

Code revision `2c3d5acc89659073a9e658e721077b6372950379`:
[successful run 37984387855](https://github.com/TIR3D4/Telegram-Agent-Control/actions/runs/37984387855), job `114002594413`.

| Command / gate | Recorded result |
|---|---|
| `ruff check tac scripts tests` | All checks passed |
| `ruff format --check tac scripts tests` | Passed |
| `mypy --follow-imports=silent --ignore-missing-imports tac/gateway.py tac/oauth.py tac/security.py tac/body_limit.py tac/observability.py` | Success, five source files |
| `bandit -q -r tac scripts -ll` | Exit 0; medium/high gate |
| `pip-audit --disable-pip --no-deps -r requirements.lock` | No known vulnerabilities found |
| `pytest -q` (SQLite) | **474 passed, 3 skipped**, 39.24 s |
| `TEST_DATABASE_URL=… pytest -q` (disposable PostgreSQL 17) | **477 passed**, 44.84 s |
| `alembic upgrade head; alembic check; alembic downgrade base; alembic upgrade head` | Passed; no schema drift detected |
| `bash -n scripts/tacctl scripts/install.sh`, `node --check` for both console scripts | Passed |
| `npm ci`, `npm audit --audit-level=high` | Zero reported vulnerabilities |
| `npm test` | **3 Playwright tests passed**, 8.7 s |
| `docker build -t tac:ci .` | Passed |
| `python scripts/ci_smoke.py` | Readiness/worker, unsent draft + media, verified backup/restore, execution pause, data-preserving uninstall/reinstall and same-revision rollback passed |

Rollback evidence is for same-revision mechanics, not arbitrary cross-release downgrade compatibility. Browser screenshots are CI artifacts (`browser-evidence`); existing README screenshot is explicitly labeled v0.1.

## Final credential-hardening local check

Code revision `b551ac5881b8350153684614143169861520596a` adds the legacy-key disable switch, fresh-install default and one regression test.

- `.venv/bin/pytest -q`: **475 passed, 3 skipped in 9.22 s**. Skips are PostgreSQL-specific; no local PostgreSQL/Docker daemon was available.
- Ruff check/format, focused mypy and Bandit medium/high gate: passed.
- The 17-test governance file independently passed after the change.
- Additional remote CI evidence for this revision is recorded below when complete; earlier revision's CI is not presented as this revision's run.

## Coverage interpretation

Many tests are parameterized registry/transport cases. Counts do not mean hundreds of independent live Telegram scenarios. New tests exercise authentication, scope/channel/creator isolation, request/daily quotas, expiry/revocation/rotation, human approvals, body bounds, native button validation, media references, OAuth claim validation and metadata, all 42 tool invocations, simultaneous MCP identities, retention, archive corruption/traversal, optional trace redaction and PostgreSQL contention.

Failed intermediate tests were corrected before delivery: SDK structured output required typed dict annotations; the reviewed-emoji fixture initially lacked review status; an environment-disabled OpenTelemetry SDK needed explicit test configuration. No production workaround or gate suppression was used.

Not tested: actual Telegram delivery/permissions, live OAuth provider/client linking, MTProto (not implemented), external OTLP collector, independent penetration test, production load, arbitrary cross-release rollback, Ubuntu host provisioning. See [TESTING.md](TESTING.md) to reproduce and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for boundaries.
