# Test results — 2026-10-09

## v0.3 connection update (local verification)

- SQLite suite: **491 passed, 3 skipped** (PostgreSQL-only cases skipped locally).
- Playwright: **4 passed**, including 390×844 phone viewport password login, session reload, connection discovery, API key creation and logout; desktop and MCP behavior also covered.
- Ruff lint/format, focused mypy, Bandit medium/high, shell/JavaScript syntax and diff whitespace checks passed.
- A disposable Keycloak **26.8.0** instance successfully ran realm/user/scope/audience provisioning twice and created an OAuth client using the restricted realm service account. A real browser Authorization Code + PKCE S256 flow and confidential token exchange also returned HTTP 200 with the expected subject, scopes and `/mcp` audience. This used local H2 development storage, not the deployment PostgreSQL/Compose stack.
- No live Telegram messages were sent. Production VPS deployment and actual ChatGPT mobile linking are **not verified** by these tests. The deployment command must be run on the VPS; the cloud connection must be registered in ChatGPT.

Full CI for code commit `5e2fb0166e0e050a22d41420615ee8cfa8c6a25a` passed in
[run 38001596955](https://github.com/TIR3D4/Telegram-Agent-Control/actions/runs/38001596955):
SQLite **491 passed, 3 skipped**; PostgreSQL **494 passed**; browser **4 passed**;
migration roundtrip, dependency audit, Docker build and Compose backup/restore/
rollback smoke all passed. This validates the application stack; managed OAuth
provisioning was verified separately against the disposable Keycloak instance
as described above, not against the production VPS.

Previous release evidence below remains scoped to its stated commits.


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

## Final code revision CI

Code revision `b551ac5881b8350153684614143169861520596a`:
[successful run 37985363329](https://github.com/TIR3D4/Telegram-Agent-Control/actions/runs/37985363329), job `114005892678`.

- SQLite: **475 passed, 3 skipped in 26.59 s**.
- PostgreSQL 17: **478 passed in 51.35 s**.
- Playwright: **3 passed in 6.8 s**.
- Ruff check/format, five-module mypy, Bandit medium/high, locked Python advisory audit, npm audit, migration roundtrip/schema drift and shell/JS checks: passed.
- Docker image build and Compose readiness/worker, verified backup/restore, execution pause, data-preserving uninstall/reinstall and same-revision rollback: passed.
- No known Python vulnerabilities / zero npm advisory findings were reported on this run's date.

The following documentation/schema-export commit `387affb1e21146a3847cbc28b2bf2a8d6a56e8f2` and final evidence-only documentation changes do not alter the runtime tested above. Their independent CI runs may be viewed on [PR #1](https://github.com/TIR3D4/Telegram-Agent-Control/pull/1). Local documentation links and tracked secret-pattern/local-path checks passed; these checks are not a full secret-scanner certification.

## Coverage interpretation

Many tests are parameterized registry/transport cases. Counts do not mean hundreds of independent live Telegram scenarios. New tests exercise authentication, scope/channel/creator isolation, request/daily quotas, expiry/revocation/rotation, human approvals, body bounds, native button validation, media references, OAuth claim validation and metadata, all 42 tool invocations, simultaneous MCP identities, retention, archive corruption/traversal, optional trace redaction and PostgreSQL contention.

Failed intermediate tests were corrected before delivery: SDK structured output required typed dict annotations; the reviewed-emoji fixture initially lacked review status; an environment-disabled OpenTelemetry SDK needed explicit test configuration. No production workaround or gate suppression was used.

Not tested: actual Telegram delivery/permissions, live OAuth provider/client linking, MTProto (not implemented), external OTLP collector, independent penetration test, production load, arbitrary cross-release rollback, Ubuntu host provisioning. See [TESTING.md](TESTING.md) to reproduce and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for boundaries.
