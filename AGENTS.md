# Repository instructions

- Read README and docs/ARCHITECTURE.md before changing execution behavior.
- Use the existing operation state machine for all Telegram writes. Never bypass owner approval via a new route or MCP tool.
- Keep bot tokens, keys, production identifiers and media out of commits and logs.
- Pin the official API snapshot; update scripts/sync_api.py rather than inventing methods.
- Run behavior tests for queue, approval, scheduling and uncertain-result changes. Test PostgreSQL for concurrency changes.
- Update matching docs and CHANGELOG. Report mocked versus live verification accurately.
