# Mobile assistant verification

Baseline: `1dd50cf3271bfe01e24300aa8a53c173a47d4389`. Candidate: `engineering/mobile-assistant`. No production deployment, live Telegram write or paid inference was performed.

## Local results

| Command / check | Actual result |
|---|---|
| `.venv/bin/python -m pytest -q` | **509 passed, 4 skipped**. Three existing PostgreSQL-only tests and one new chat row-lock test skipped on local SQLite. |
| `npm test -- --project=chromium` | **6 passed**. Includes 390×844 Persian chat, session reload, persisted queue/cancel, secret-free config response, escaped HTML and no horizontal overflow. |
| `ruff check tac scripts tests` and `ruff format --check tac scripts tests` | Passed. |
| `mypy --follow-imports=silent --ignore-missing-imports tac/gateway.py tac/oauth.py tac/security.py tac/body_limit.py tac/observability.py` | Passed (5 modules). Does not claim all-module typing. |
| `bandit -q -r tac scripts -ll` | Passed. |
| `alembic upgrade head` / `alembic check` | Passed; single new head, no missing model migrations. |
| Previous-schema migration / pause-before-migrate / downgrade-upgrade roundtrip | Isolated SQLite behavior test passed. Existing schema starts at `9906fa12eb62`; downgrade removes only the new chat table in this test. No production rollback. |
| Shell/JS syntax and `git diff --check` | Passed. |

Tests exercise: encrypted provider and grant secrets, private vault permissions, owner-only config/history, revoked grant denial, exact operation ownership/channel policy, daily quota through shared REST, duplicate prevention, read-only queued/worker/status flow with mock Telegram, independent human approval, unknown shell/deploy/approve tool rejection, cancellation while model response is pending, interrupted turn without replay, pause state, provider auth headers and bounded request schema for all three configured providers, no retry/body leak on provider failure, verified vault backup member and cross-revision rollback denial.

The Telegram adapter and paid provider responses in these tests are **mocked**. Actual HTTP requests through the local ASGI REST application and actual local browser interactions are exercised. The new read-only connection-test button queues a real getMe when installed; its local test uses no live Telegram credentials.

## Remote / device checks

- From this environment, HTTPS GET to the owner's `/health/ready` returned HTTP 200 **HTML “Site Unavailable”**, not the application's JSON. This is not counted as a passing application health check. No authenticated new-chat API connection could be established here.
- Earlier user-provided server output showed ready JSON and successful getMe for the existing gateway. That evidence does not prove the new chat/provider path works after upgrade.
- WebKit browser package downloaded; local `playwright install-deps webkit` failed because the container cannot change system group/user IDs for apt. Local WebKit and physical Safari remain unverified.
- CI is configured to run Chromium and iPhone-emulated WebKit on a runner with system dependencies, the full PostgreSQL suite, migration roundtrip and Docker backup/restore smoke. CI results must be recorded after the candidate commit runs; configuration alone is not evidence of success.
- Physical iPhone keyboard, Home Screen/standalone installation, paid provider/model tool support and the new assistant's live authenticated getMe are outstanding installation acceptance checks.

## Deployment boundary

The upgrade helper has explicit branch/commit guards, existing configuration preservation, backup handling, migration-head inspection, readiness and fresh worker-heartbeat checks, paused execution and private failure reports. Local tests verify selected helpers/migration/rollback guards. Full Docker install/upgrade on the owner's Ubuntu server has not been performed. CI Compose tests validate image/start/backup/restore/same-revision rollback, not all external OAuth/client registration or production networking.

## Completed GitHub CI

Code commit: `b22099b5c1d0092782ba91950c895187c966a976`.
[Run 38006832752](https://github.com/TIR3D4/Telegram-Agent-Control/actions/runs/38006832752), job `114077436584`: **success**, completed 2026-10-10 UTC.

Actual decoded job logs record:

- SQLite: **509 passed, 4 skipped** (37.32s).
- PostgreSQL: **513 passed** (54.82s), including the new concurrent chat claim test.
- Chromium + iPhone-emulated WebKit: **12 passed** (20.8s); six tests per browser.
- Ruff/format, five-module mypy, Bandit, Python and npm dependency audit: passed; no known vulnerabilities reported by those scans.
- PostgreSQL migration roundtrip and `alembic check`: passed.
- Docker image build and Compose readiness: passed.
- Verified backup/restore, unchanged grant ID and decryptable restored fake provider key/vault: passed.
- Same-revision rollback and data-preserving uninstall/reinstall: passed.

Browser evidence artifact: `browser-evidence`, artifact ID `11651348952`, available from the run. These are real browser screenshots of the test application, not production or fabricated UI.

CI uses isolated test credentials and does not prove paid inference, live Telegram connectivity, physical iPhone Safari, existing external OAuth provisioning, or the complete upgrade on the owner's Ubuntu host. Earlier candidate runs also passed; the counts above belong to the exact final code commit. A later documentation-only commit records this evidence without changing executable code.
