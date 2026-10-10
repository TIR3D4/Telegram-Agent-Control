# Development audit — 2026-10-10

Repository: `TIR3D4/Telegram-Agent-Control`. AUTOPOST originally contained only an empty Git repository; no existing work was removed. `main` at `faf2b9d` lacked the requested handoff. Starting point: `engineering/codex-handoff` at `c80778a3833b90bee66925e9c658896cc60b43bb`. Review branch: `codex/handoff-audit`; [draft PR #6](https://github.com/TIR3D4/Telegram-Agent-Control/pull/6). Application fixes through `544fb0372a8baa483cad9d4538dddc24a2e58b99`.

## Verified code paths

- `remote_mcp.AuthenticatedMCP` rejects owner credentials and binds caller credentials to request context; `mcp_server.call` forwards them to authenticated REST. Stdio uses its configured scoped credential. `security`, `gateway`, `operations` and `workflows` supply shared policy/state transitions.
- Grants constrain methods, channels and ownership. Quotas are database-backed; idempotent replay compares content without another operation charge. Human approval binds the exact content/media/schedule digest and expires. Revision revokes approval.
- Media uses multipart REST or Base64 MCP (1 MiB decoded); stored asset IDs bind to draft attachments and worker multipart delivery. Actual host file access or a genuine download link is still required.
- Durable schedules/workflows and worker leases persist in SQLAlchemy/PostgreSQL. Worker rechecks permissions/approval and fences completion. Uncertain writes are not blindly resent. Status and audit are observable through REST/MCP; submission is not delivery.
- Connection profiles exist for REST, MCP, Codex, Claude and ChatGPT. The separate private ChatGPT bridge supports sequential content-plan drafts, byte upload and owner review links. Plans are not atomic publish batches. The console remains the independent approval surface. No new chat or agent shell was added.
- Installer/Compose provision API, worker, PostgreSQL and migrations. Upgrade supports a pinned commit, backup/config preservation, migration, readiness/heartbeat/doctor and paused execution. Backup verifies checksums/archive paths. `tacctl doctor` aggregates bounded host, services, database, worker, REST/MCP, OAuth and Telegram read probes with safe reports. These are code findings, not live installation certification.

## Fixed in this review

1. Development bootstrap failed on this Windows host because it assumed working `python3` and `.venv/bin/python`. Added interpreter selection/native venv paths; setup subsequently completed. POSIX terminal collection now skips explicitly without `pty`.
2. MCP raised JSON/attribute exceptions on HTML, empty or non-object gateway error responses. Three failing regression cases reproduced this. It now returns a safe structured error with original-key reconciliation guidance, without raw response text or automatic retries.
3. Direct restore verified integrity but omitted the cross-revision guard used by rollback. It now requires an exact backup/checkout commit match before confirmation/service stop. Integrity-only inspection of old snapshots remains available. This conservative policy may reject compatible revisions; cross-revision recovery needs a separately reviewed plan. Tests cover same/different commits and the actual shell entrypoint with fake Docker, never a real database restore.

## Verification and limits

- Existing optimizer doctor/context analysis completed; all eight tracked vendor blobs match the pinned SHA-256 manifest. No reinstall. Local CRLF conversion is distinct from canonical Git blobs.
- Windows Python 3.14.4 setup succeeded after one interrupted download. `pip check`, Ruff lint/format, security-boundary mypy, Bandit and Bash syntax passed.
- Full disposable SQLite suite before restore changes: **537 passed, 5 skipped, 2 failed**. Failures: Unix `0600` assertions in `test_secret_storage_and_response_boundaries` and `test_upgrade_failure_report_is_private_and_has_commit`. Windows did not report that mode; failures were not suppressed or counted as passes. Skips: four PostgreSQL cases and POSIX terminal test.
- After restore changes: **107 focused tests passed** (MCP, all tool protocol cases, governance, operations, workflows, doctor, lifecycle). Lifecycle with the additional shell regression then passed **11 tests**; counts overlap. Disposable SQLite/media and mocked Telegram only. An existing pytest temporary-directory access error was avoided with a fresh directory inside the ignored development venv.
- Private ChatGPT bridge: **18 mocked tests passed**; no hosted bridge contacted. SQLite migration roundtrip passed within the full suite. PostgreSQL migrations/concurrency, browsers and Compose backup/restore require isolated Linux CI. Docker is absent locally. PR #6 triggered CI; inspect its exact final head before claiming those gates passed.
- Not verified: production SSH, actual client accounts, live Telegram/media delivery, physical iPhone, current server doctor or existing failed operation. No publication, production configuration change, deployment or real database rollback occurred. Repository access is separate from runtime access; manifest/proxy changes do not guarantee host-account capabilities.

## Priorities

1. Review exact-head Linux/PostgreSQL/browser/Compose CI, including restore protection, before release. Windows production permission semantics are not certified.
2. With separately scoped access, verify initialize/tools/list/inspect_system for each actual client, then media upload and drafts. Live publication needs explicit authorization and independent owner approval.
3. Use separately authorized read-only server access for current doctor, worker/queue/backup and the historical failed operation. Do not resume/retry unseen work. Deploy only an explicitly approved commit with backup, migration and health review; assess compatibility separately for cross-revision recovery.
