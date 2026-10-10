# Current handoff — 2026-10-10

Goal: maintain TAC as a Telegram control plane used from external ChatGPT/Codex/Claude conversations; console handles connections, independent owner approval and operations. No new chat or agent shell.

Checkout: `codex/handoff-audit`, based on `engineering/codex-handoff` at `c80778a`; application fixes through `544fb03`. Draft PR #6: https://github.com/TIR3D4/Telegram-Agent-Control/pull/6. See `docs/CODEX_AUDIT.md` for independently verified evidence and priorities. Older handoff reports remain historical only.

Fixed: Windows Git Bash setup/PTY collection; malformed MCP gateway responses with no automatic resend; direct restore rejects different backup commit before service mutation. No dependency/schema/approval-policy change. Existing optimizer used, all 8 tracked vendor hashes verified; no reinstall.

Verified locally: setup, lint/format, mypy boundary, Bandit, Bash syntax, 18 mocked bridge tests. Full Windows SQLite run before restore fix: 537 pass / 5 skip / 2 Unix-mode assertion failures. After fix: 107 focused passes; lifecycle including shell regression 11 passes (overlapping counts). CI triggered; inspect exact final PR head before claiming green PostgreSQL/browser/Compose gates. Docker absent locally.

Unverified: actual client accounts, VPS/current doctor, live media delivery and old failed operation. No production access, publication or deployment performed. Next: final CI review, then separately scoped read-only client/server checks. Deployment needs explicit authorization on a known commit with backup/migration/health review. Never retry uncertain work or restore across revisions without compatibility review.
