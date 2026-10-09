# Implementation report — v0.2 hardening

Date: 2026-10-09. Repository: TIR3D4/Telegram-Agent-Control. Branch: `engineering/production-hardening-v0.2`. Baseline: `faf2b9d73f7c687a2ad2cfd07bdac92f605941fb`. No default-branch rewrite, merge or production deployment.

## Reviewable changes

| Commit | Change |
|---|---|
| `82762a6325ff34060e5ec23d0c72e9ccab1a47e0` | Source audit of 15 references, gaps, implementation plan and gateway ADR |
| `f6cbebed2695d0b7d5f8e6a595aa3cad41abaf74` | Shared scoped gateway, finite grants, OAuth resource verification, expiring approvals, MCP tool expansion, migrations and diagnostics |
| `2c3d5acc89659073a9e658e721077b6372950379` | Governance/media/keyboard/maintenance console, verified backup/restore/rollback, protocol/security/browser/PG CI |
| `b551ac5881b8350153684614143169861520596a` | Disable legacy shared agent/reader credentials on fresh installs; opt-out also stops queued legacy execution |

Documentation commits follow these code changes; consult the branch history for their exact IDs.

## Implemented and preserved

- Preserved the existing Bot API registry/transport, media/emoji catalog, operations, durable workflows, PostgreSQL queue and console. No unnecessary framework rewrite.
- Added per-agent identity and scoped expiry/rotation/revocation, exact method/chat authorization, source-chat checks, ownership, atomic quotas and execution-time policy revalidation. Remote MCP preserves each caller's identity and rejects owner credentials.
- Added external-issuer OAuth resource verification (RS256/ES256, fixed issuer/JWKS/audience, required claims and subject binding) and protected-resource metadata. No homegrown login/authorization server.
- Made human consent finite and exact. Revisions revoke approval. Destructive maintenance requires exact-digest owner approval and single-use execution. Restore produces a fixed operator command rather than exposing a shell.
- Expanded to 42 real tools covering drafts/status/history/preview/duplicate/safe retry, media, native keyboards, workflows, channels/accounts, safe config/database, logs/traces/metrics and maintenance requests. All have actual SDK discovery schemas and protocol-to-REST tests.
- Added API/UI grant management, asset library, compact keyboard builder, channel connection status, worker metrics/settings and maintenance review. Kept the generic method editor for broad Telegram coverage.
- Added request/operation correlation, secret redaction, optional OTLP spans, bounded request bodies, finite Telegram retry attempts, graceful worker shutdown, bounded retention and safe diagnostics.
- Added versioned migrations, manifest verification including media archive path safety, paused upgrade/restore, local restore receipts, rollback mechanics and data-preserving uninstall.
- Added lint/format, focused mypy, Bandit, Python/npm advisory audits, protocol/authorization/OAuth/media/keyboard/retention/archive/telemetry tests and browser/PG/Compose CI.

## Evidence and acceptance

[TEST_RESULTS.md](TEST_RESULTS.md) records exact commands, counts and CI links. Tests use mocks, fixture media and synthetic credentials. All 42 tools are invoked through MCP against the real REST app; this is stronger than discovery-only coverage but is not live Telegram proof. Docker/Compose, PostgreSQL, migration roundtrip, backup/restore and same-revision rollback were exercised in GitHub Actions.

[RESEARCH_COMPARISON.md](RESEARCH_COMPARISON.md) pins reference source commits, paths, licenses and observed maintenance/test structure. No source was copied from those projects and their test suites were not executed. Major choices are justified in ADRs; broad research stopped after those decisions.

## Partial or deliberately separate

The master request is not represented as 100% production acceptance. One Bot API account is supported; MTProto/multi-account sessions, a model-driven internal Agent Runtime, owner SSO/MFA, full localization/specialized editors, native reach analytics and arbitrary historical message retrieval are not implemented. The persistent deterministic runtime is retained. OAuth login/PKCE/registration needs an external provider and a live client test. Whole-project strict typing, external penetration/load tests, live collector deployment and cross-release rollback remain unverified.

The console has a simple terminal menu companion, not a full terminal dashboard. Configuration application and bootstrap-secret/account removal remain local operator procedures. Every material boundary is in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) and [CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md).

## Operator handoff

Use the branch-specific commands in [INSTALLATION.md](INSTALLATION.md) on staging first. Configure a domain, external issuer if needed, and finite agent grants. Use an authorized test bot/channel to verify getMe/getChatMember and required post/media/slideshow/emoji behavior. Obtain explicit authorization before production installation or channel publishing. No live credentials from the conversation were placed in code, docs, logs or tests.
