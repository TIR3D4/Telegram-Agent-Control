# Historical v0.1 validation

This file records the baseline release. Current upgrade evidence is in [TEST_RESULTS.md](TEST_RESULTS.md), reproduction in [TESTING.md](TESTING.md), and limitations in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

# Validation and release status

This file records evidence, not a blanket production-readiness claim.

## Local checks on 2026-10-09

- **398 passing Python tests**, including 185 method-schema cases and 185 mocked method-transport cases. Two PostgreSQL-only tests for concurrent claims and late-response recovery are skipped on local SQLite.
- Behavior checks cover owner-only approval, content revision invalidation, idempotency conflicts, time-based scheduling, cancellation, lost responses, rate-limit retry, stale-lease recovery, sequential/delayed automation, webhook deduplication, multipart transfer, emoji label preservation and MCP authentication/tool discovery.
- Two Playwright scenarios passed (console workflow and authenticated remote MCP tool execution). Console checks include: login, dashboard, draft creation, schema validation, API explorer, other console views and mobile layout. Screenshots were visually reviewed. No Telegram message was sent by this test.
- Ruff lint/format, Python compilation, shell syntax and JavaScript syntax checks passed.
- SQLite Alembic migrations applied locally. The workflow contains PostgreSQL migration roundtrip, PostgreSQL behavior tests, Docker image build and Compose API/worker readiness smoke checks.

## CI status

**Verified successful:** [GitHub Actions run 37980414095](https://github.com/TIR3D4/Telegram-Agent-Control/actions/runs/37980414095), code commit `ef4c57c2b04045cdea1fc6622bd7ffb1346b0086`, 2026-10-09.

- SQLite: **398 passed**, two PostgreSQL-only cases skipped.
- PostgreSQL 17: **400 passed**, including concurrent claim protection and recovery versus late-response locking.
- Alembic upgrade, drift check, downgrade and re-upgrade succeeded.
- Two Playwright scenarios passed, including an authenticated remote MCP tool call.
- Docker image built successfully; Compose migrated the database and started the API and worker.
- A draft operation and uploaded file survived backup/restore; restoration paused execution as designed.
- Uninstall preserved persistent volumes; restarting restored access to the same file and paused state.

These installation checks used synthetic credentials and never sent a Telegram message. Docker/PostgreSQL were exercised in GitHub Actions, not the local authoring runtime. The documentation-only commit recording this evidence does not change executable code.

## Live acceptance still required

A deployed bot must be verified using getMe/getChatMember from its actual VPS. Confirm each required content format in a test channel, especially rich slideshows and premium custom emoji eligibility. Confirm media limits, administrator rights, client rendering, TLS/DNS, webhook delivery and restoration before using a main channel.

All 185 methods have generated input contracts and share a tested transport. **They have not all been executed against live Telegram.** Validation captures field types/required fields/unknown fields and selected conditional rules; remaining semantic restrictions are documented from Telegram and enforced upstream. No unsupported destination capability is promised.
