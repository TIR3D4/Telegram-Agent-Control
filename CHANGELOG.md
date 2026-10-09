# Changelog

## 0.2.0 — hardening candidate, 2026-10-09

Scoped expiring agent identities, OAuth resource-server verification, caller-preserving MCP, 42 tested tools, finite human approvals, resource isolation and quotas. Added governance/media/keyboard/maintenance console panels, correlated diagnostics/optional tracing, verified backups/controlled rollback, safe fresh-install defaults and expanded protocol/PostgreSQL/browser/security CI. See `docs/IMPLEMENTATION_REPORT.md` and `docs/KNOWN_LIMITATIONS.md`; no production deployment or live OAuth/Telegram acceptance is claimed.

Worker completion and owner reconciliation lock the operation row, preserving recovery decisions when a late Telegram response arrives concurrently. Deployment CI exercises database/media backup, paused restore and data-preserving uninstall/reinstall.

## 0.1.0 — 2026-10-09

Initial control-plane release: Bot API 10.3 registry, authenticated REST/MCP, web and terminal consoles, PostgreSQL operations and audit, owner approval, timestamp/cron/event automation, visual emoji catalog, media uploads, Docker install/update/backup/restore/uninstall, and automated validation. Live Telegram deployment remains an operator acceptance step.
