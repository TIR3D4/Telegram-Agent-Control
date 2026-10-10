# Codex development handoff

For the subsequent repository takeover, fixes and independently rerun checks, read [development audit](CODEX_AUDIT.md). The results below describe the original handoff and remain historical evidence only.

Select repository `TIR3D4/Telegram-Agent-Control`, branch `engineering/codex-handoff`. This branch includes the working v0.4 application plus project-local context tooling and concise handoff notes. It does not migrate your ChatGPT conversation, credentials, plugin installation or server access into Codex.

## Start prompt

```text
Read AGENTS.md, .context/CURRENT_TASK.md and docs/CODEX_HANDOFF.md.
Use the already installed .codex-context/AUTO_MODE.md guidance automatically.
Understand the existing Telegram Agent Control architecture and verify the development environment with relevant tests. Keep conversations in external AI clients, preserve independent owner approval and existing data, and work through reviewable changes. Do not deploy or send Telegram messages for onboarding. Give a brief current-state assessment, then continue with my requested task.
```

Use `bash scripts/codex_setup.sh` as the environment setup command if the environment supports setup commands, or run it in the checkout terminal. It needs Python 3.12+, venv support and package-download access. No production `.env`, bot token, owner key, database or SSH credential is needed to run unit tests. The script installs development dependencies only; it does not create a cloud environment or register a client connection.

## Navigation / validation

On Windows with Git Bash, setup also accepts `python` when the `python3` launcher is unavailable and uses `.venv/Scripts/python.exe`. Set `PYTHON` to an explicit interpreter path if needed. Use `.venv/Scripts/python.exe -m pytest -q` for local tests. The POSIX terminal test is skipped on Windows; Docker/PostgreSQL, Unix file-permission and browser acceptance still need their supported environments. A successful dependency install alone does not verify those gates.

Read `.context/SOURCE_INDEX.md` before opening only the files relevant to the task. Read README.md and docs/ARCHITECTURE.md when modifying execution behavior.

```bash
# Unit and behavior suite; test fixtures use disposable SQLite by default
.venv/bin/python -m pytest -q
# Select a focused file first for small changes
.venv/bin/python -m pytest -q tests/test_doctor.py
.venv/bin/ruff check tac scripts tests
.venv/bin/ruff format --check tac scripts tests
# Bridge tests, no production connection
node --test integrations/chatgpt-cloud/tests/connector.test.mjs
# Optional browser acceptance in a supported dev environment
npm ci
npx playwright install --with-deps chromium webkit
npm test
```

PostgreSQL tests need a **disposable** database via `TEST_DATABASE_URL`; tests drop/recreate tables. Never point tests at production. Full gates and migration/Compose lifecycle checks are defined in `.github/workflows/ci.yml`. `scripts/ci_smoke.py` writes a test `.env` and removes Compose volumes; run only in an isolated checkout/runner with no real installation data. Docker and browser dependencies may not be available in a hosted coding environment: report that rather than claiming those gates passed.

## Installed optimizer

Pinned source: `TIR3D4/codex-context-optimizer` at `a19f394e95d79dbd68aca5ab28e222b53d30ac99` (MIT). Runtime scripts, AUTO_MODE and templates are copied unchanged into `.codex-context/`, with license and hashes in UPSTREAM.json. This project-local installation is intentional: the inspected upstream shell bootstrap clones/resets a global tool checkout and optionally installs third-party helpers, while this handoff needs only the compact runtime. No global bootstrap was executed.

Root AGENTS.md activates compact navigation and automatic context guidance. Future normal tasks do not need a repeated setup prompt. The optimizer cannot force a client to obey instructions, change model limits or make unavailable account features appear.

```bash
python3 .codex-context/tools/codex-context.py doctor --repo .
python3 .codex-context/tools/work-context.py analyze --repo .
```

These are **development context** checks, different from `scripts/tacctl doctor`, which diagnoses an installed TAC server. Atlas and CatchUp are optional and not installed by this handoff. No Atlas map is fabricated. Telemetry availability depends on the host; no measured token savings are claimed. Local telemetry, benchmark baselines and generated handoffs are git-ignored; never commit conversation logs or secrets.

## Known deployment snapshot and limits

The owner's last reported deployed application was commit `63617abf6cb1b429ca1653a10addd64a249571ba`. The 2026-10-10 09:49 UTC report showed 21 PASS, 2 WARN, 0 FAIL, 4 SKIP. Execution was paused, an OS reboot was pending, and one historical failed operation existed outside the connected agent's visibility. Do not infer current state or resume/retry it automatically.

Historical CI for that exact app commit: https://github.com/TIR3D4/Telegram-Agent-Control/actions/runs/38042038312 — SQLite 537 passed/4 skipped, PostgreSQL 541 passed, browser 22 passed, Compose diagnosis/authenticated MCP/backup and restore lifecycle passed. This is historical evidence, not tests of future edits. Real Codex/Claude account connection, physical iPhone Safari and live media delivery remain unverified.

The private ChatGPT bridge source is under `integrations/chatgpt-cloud`; its hosted deployment is separate from the VPS. Do not create a replacement public bridge, replace OAuth or copy secrets from prior chats. Connecting Codex to TAC uses a separately provisioned scoped credential and a client-supported connection method. Repository management and Telegram runtime access are separate capabilities.

Future release: implement and test in a review branch, present diff/PR and pinned commit, preserve backups/configuration/OAuth, assess migrations, then use the reviewed upgrade path after explicit deployment authorization. Never run database rollback without compatibility review. Do not claim SSH or production access unless actually verified.

## Handoff verification

This change touches development tooling and documentation only. Verify copied runtime hashes against UPSTREAM.json, Python syntax, shell syntax, optimizer doctor and compact-context analysis. No deployment, Telegram publication or real Codex-hosted session is performed by adding these files. Application behavior tests need not be rerun solely for documentation/vendor copies; existing CI remains available for subsequent behavior changes.

Checks performed for this handoff: all 8 copied upstream files matched recorded SHA-256 hashes; Python compilation and shell syntax passed; optimizer doctor ran (Atlas/CatchUp absent); compact context analysis completed; existing `tests/test_doctor.py` passed 22 tests against the local development environment. The new dependency-install script was syntax-checked, not executed in a fresh Codex host. No live deployment or live Telegram test was performed for the handoff.
