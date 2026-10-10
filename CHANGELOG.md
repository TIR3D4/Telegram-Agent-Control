# Changelog

## Setup hotfix — non-seekable SSH terminal

- Read and write `/dev/tty` through separate streams so the piped updater can prompt on non-seekable terminals.
- Added a real PTY regression test with redirected stdin and hidden password entry.
- If v0.3 already built and stopped at the username prompt, pull this fix and run `bash scripts/tacctl setup`; no rebuild or full upgrade is needed.

## 0.3.0 — Console access and managed connections

- Responsive username/password login with hashed credentials, expiring HttpOnly sessions, CSRF checks and login rate limiting.
- Web connection center for independent REST and remote MCP paths, scoped API key issuance, agent guide and exact-callback OAuth client creation with PKCE.
- One setup command provisions managed Keycloak services, login, resource audience and scopes. Existing manual OAuth installations retain their database, subjects, grants and secrets.
- Backed-up one-command upgrade adopts only known local Caddy/ignore customizations and preserves independent owner approval. Execution remains paused for review after upgrade.
- Explicit cloud MCP registration guidance: a remote URL in a ZIP alone does not guarantee ChatGPT mobile availability.


## 0.2.0 — hardening candidate, 2026-10-09

Scoped expiring agent identities, OAuth resource-server verification, caller-preserving MCP, 42 tested tools, finite human approvals, resource isolation and quotas. Added governance/media/keyboard/maintenance console panels, correlated diagnostics/optional tracing, verified backups/controlled rollback, safe fresh-install defaults and expanded protocol/PostgreSQL/browser/security CI. See `docs/IMPLEMENTATION_REPORT.md` and `docs/KNOWN_LIMITATIONS.md`; no production deployment or live OAuth/Telegram acceptance is claimed.

Worker completion and owner reconciliation lock the operation row, preserving recovery decisions when a late Telegram response arrives concurrently. Deployment CI exercises database/media backup, paused restore and data-preserving uninstall/reinstall.

## 0.1.0 — 2026-10-09

Initial control-plane release: Bot API 10.3 registry, authenticated REST/MCP, web and terminal consoles, PostgreSQL operations and audit, owner approval, timestamp/cron/event automation, visual emoji catalog, media uploads, Docker install/update/backup/restore/uninstall, and automated validation. Live Telegram deployment remains an operator acceptance step.

## Mobile assistant candidate

- Add Persian server-side chat, encrypted provider/grant storage and durable bounded tool turns over the existing REST policies.
- Add independent owner review links, read-only getMe connection test and development specification records.
- Preserve login/OAuth on upgrade; support explicit reviewed commit, private upgrade reports and optional console-only initial setup.
- Include vault in verified backups; block unreviewed cross-revision database rollback.
- Add iPhone viewport/WebKit CI coverage and denial/idempotency/quota/provider-boundary tests.

## ChatGPT cloud control candidate — 2026-10-10

- Restore in-ChatGPT control as the goal; standalone chat remains optional.
- Add a private cloud MCP-to-REST connector with per-user encrypted scoped credentials, bounded tools and media import.
- Add owner review deep links, Tehran schedule display and authenticated attachment previews.
- Preserve the existing gateway, scheduler, OAuth, data and independent approval. No production deployment or live connection claimed.
