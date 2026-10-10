# Durable decisions

- Keep a shared API-first modular monolith and shared authorization; client-specific connection profiles do not mean separate backends.
- External AI clients are primary. The internal chat is optional and must not replace the owner's requested ChatGPT/Codex/Claude workflow.
- Agent prepares; independent owner approves exact writes. Never silently change this rule for convenience.
- Telegram control credentials and development/deployment access remain separate. A working repository checkout does not establish a live client connection.
- Preserve installed users, OAuth, secrets, data, schedules and media. No unreviewed database downgrade; release uses pinned commit, backups, migration checks and health/worker verification.
- Production doctor is read-only diagnosis, not the destructive isolated CI suite. PASS/WARN/FAIL/SKIP are distinct; exit 2 is warnings/skips, not installation failure.
- Optimizer is vendored with upstream MIT license and checksums at a pinned revision. It is not installed globally, not part of the runtime image, and no token-saving percentage is claimed.
