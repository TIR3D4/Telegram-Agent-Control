# Changelog

Worker completion and owner reconciliation lock the operation row, preserving recovery decisions when a late Telegram response arrives concurrently. Deployment CI exercises database/media backup, paused restore and data-preserving uninstall/reinstall.

## 0.1.0 — 2026-10-09

Initial control-plane release: Bot API 10.3 registry, authenticated REST/MCP, web and terminal consoles, PostgreSQL operations and audit, owner approval, timestamp/cron/event automation, visual emoji catalog, media uploads, Docker install/update/backup/restore/uninstall, and automated validation. Live Telegram deployment remains an operator acceptance step.
