# Changelog

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
