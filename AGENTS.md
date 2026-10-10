# Repository instructions

- Read README and docs/ARCHITECTURE.md before changing execution behavior.
- Use the existing operation state machine for all Telegram writes. Never bypass owner approval via a new route or MCP tool.
- Keep bot tokens, keys, production identifiers and media out of commits and logs.
- Pin the official API snapshot; update scripts/sync_api.py rather than inventing methods.
- Run behavior tests for queue, approval, scheduling and uncertain-result changes. Test PostgreSQL for concurrency changes.
- Update matching docs and CHANGELOG. Report mocked versus live verification accurately.

## Codex continuity and context

- At the first task in a session read `.context/CURRENT_TASK.md` and `.codex-context/AUTO_MODE.md`; use `.context/SOURCE_INDEX.md` to locate only relevant code. See `docs/CODEX_HANDOFF.md` for onboarding and validation commands.
- The pinned optimizer runtime is already installed in `.codex-context/tools/`. Do not clone/reinstall it for each task or read its implementation for ordinary application work. Run its health check quietly at useful task boundaries, not every turn.
- Prefer exact searches and narrow reads; expand whenever correctness requires. Preserve unrelated changes. No automatic reset/clean/stash, branch proliferation, or measured token-saving claims without telemetry.
- Keep `.context/CURRENT_TASK.md` compact and current at meaningful handoffs. Do not include credentials, production identifiers, raw logs or message content. Historical test results are not evidence for new edits.
- Developer setup is `bash scripts/codex_setup.sh`. Never run production `install`, `upgrade`, `restore`, `purge` or `scripts/ci_smoke.py` against a live checkout to prepare a development environment. CI smoke creates/deletes isolated containers and a test `.env`.
- Work in a review branch. GitHub code access does not grant VPS or Telegram access. No production deployment, publishing, approval bypass or destructive action is authorized merely by this handoff.
