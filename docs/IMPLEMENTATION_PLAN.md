# Upgrade plan and acceptance gates

1. **P0 identity and gateway:** scoped expiring/revocable agent grants, resource ownership, action/channel restrictions, no unrestricted ordinary-agent method execution. Acceptance: denied scope/channel/foreign ID and revoked queued work tests.
2. **P0 approvals:** independent owner, exact content hash, finite execution validity, workflow locking and cancellation fencing. Acceptance: expired approval and concurrent policy change tests.
3. **P0 MCP/OAuth:** preserve caller identity; JWT issuer/audience/expiry validation; protected-resource metadata; bounded structured output; shared REST errors. Acceptance: real initialize/list/call, two-identity isolation and malformed/foreign JWT tests. Live issuer/client login explicitly separate.
4. **P1 operator and tools:** typed post/media/keyboard/workflow/admin diagnostics, safe retries, channels/observed history, metrics and correlated audit. Acceptance: matching REST and MCP behavior tests.
5. **P1 lifecycle/UI:** scoped credentials management, media and keyboard editor, backup verification/restore requests, version-aware rollback, retention and safe installation. Acceptance: browser tests and Compose lifecycle CI.
6. **Delivery:** source comparison, ADRs, capability matrix, client setup, implementation report, exact test results and known limitations on dedicated branch/PR. No production deployment or default-branch rewrite.

Preserve existing working routes at `/v1`; document that compatibility prefix rather than breaking clients solely to rename it `/api/v1`. Keep a single configured bot account; MTProto and arbitrary account onboarding remain a separately scoped adapter project. Internal LLM execution is optional and not enabled without a justified provider/budget design; deterministic persistent workflows remain the execution engine.
