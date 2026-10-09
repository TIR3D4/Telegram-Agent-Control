# Testing

Use Python 3.12 and the checked-in lock. Tests set synthetic credentials and temporary storage. **No live Telegram token is required or used.**

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
ruff check tac scripts tests
ruff format --check tac scripts tests
mypy --follow-imports=silent --ignore-missing-imports tac/gateway.py tac/oauth.py tac/security.py tac/body_limit.py tac/observability.py
bandit -q -r tac scripts -ll
pip-audit --disable-pip --no-deps -r requirements.lock
pytest -q
npm ci
npm audit --audit-level=high
npx playwright install --with-deps chromium
npm test
```

PostgreSQL: point `TEST_DATABASE_URL` at a **disposable** PostgreSQL 17 database and run `pytest -q`. Test fixtures drop/recreate tables. Never point tests at production. The PG-only cases cover competing worker claims, fenced late responses and concurrent request quota enforcement.

Migration CI runs upgrade → `alembic check` → downgrade base → upgrade on disposable PG. `scripts/ci_smoke.py` writes synthetic `.env`, builds/starts Compose, verifies readiness/worker, stores an unsent draft and asset, exercises backup/verification/restore/pause/uninstall/reinstall/same-revision rollback, then destroys test volumes. Run it only in a disposable clone; it overwrites/removes `.env`.

Tests cover all 42 actual MCP tools through protocol calls against the real REST app, simultaneous identity isolation, typed discovery, OAuth claims/metadata, scopes/channel/record denial, independent approval, expiry/revocation, immutable assets, keyboard semantics, retention, archive traversal/corruption, exporter redaction, scheduling, fault/recovery and generated Telegram contracts. Telegram adapter results and preview assets are mocks/fixtures, not proof of live platform behavior.

Browser tests cover responsive console traversal, draft construction, remote diagnostics, scoped credential creation, denial of READ writes, keyboard validation, media upload and approved credential revocation. Screenshots are generated in `test-results/` and uploaded as CI artifacts; they are not fabricated product mockups.

Static security gate: Bandit medium/high severity (`-ll`), not a zero-low-findings claim. Python dependency advisory scan checks the locked requirements; npm checks UI test tooling. Advisory databases change. The mypy gate covers five security modules with silent imports; the whole project is not strict-typed. Container OS package vulnerability scanning, external penetration testing and performance benchmarks are not included.

See [exact results](TEST_RESULTS.md). For installation/user-account/Telegram production acceptance, follow [installation](INSTALL.md) and obtain explicit authorization.
