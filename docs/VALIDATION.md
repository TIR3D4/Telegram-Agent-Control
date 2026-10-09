# Validation and release status

This file records evidence, not a blanket production-readiness claim.

## Local checks on 2026-10-09

- **398 passing Python tests**, including 185 method-schema cases and 185 mocked method-transport cases. Two PostgreSQL-only tests for concurrent claims and late-response recovery are skipped on local SQLite.
- Behavior checks cover owner-only approval, content revision invalidation, idempotency conflicts, time-based scheduling, cancellation, lost responses, rate-limit retry, stale-lease recovery, sequential/delayed automation, webhook deduplication, multipart transfer, emoji label preservation and MCP authentication/tool discovery.
- Two Playwright scenarios passed (console workflow and authenticated remote MCP tool execution). Console checks include: login, dashboard, draft creation, schema validation, API explorer, other console views and mobile layout. Screenshots were visually reviewed. No Telegram message was sent by this test.
- Ruff lint/format, Python compilation, shell syntax and JavaScript syntax checks passed.
- SQLite Alembic migrations applied locally. The workflow contains PostgreSQL migration roundtrip, PostgreSQL behavior tests, Docker image build and Compose API/worker readiness smoke checks.

## CI status

Read the repository's **CI** workflow for the current commit. Docker/PostgreSQL are not available in the local authoring runtime; a checked-in workflow is not itself evidence of a successful run. This section should be updated with the verified run URL after GitHub Actions completes.

## Live acceptance still required

A deployed bot must be verified using getMe/getChatMember from its actual VPS. Confirm each required content format in a test channel, especially rich slideshows and premium custom emoji eligibility. Confirm media limits, administrator rights, client rendering, TLS/DNS, webhook delivery and restoration before using a main channel.

All 185 methods have generated input contracts and share a tested transport. **They have not all been executed against live Telegram.** Validation captures field types/required fields/unknown fields and selected conditional rules; remaining semantic restrictions are documented from Telegram and enforced upstream. No unsupported destination capability is promised.
