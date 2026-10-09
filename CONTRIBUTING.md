# Contributing

Use Python 3.12+, `requirements.lock`, and editable installation. Run `ruff check tac scripts tests`, `ruff format --check tac scripts tests`, and `pytest -q`. For database/worker changes also run PostgreSQL tests with `TEST_DATABASE_URL` and Alembic migration checks.

Do not edit registry fields manually to pretend unsupported methods exist. Regenerate from official docs and review diffs. Preserve source attribution. New execution paths must pass through the operation/approval policy; add tests for retries, cancellation, revision races or timeouts as relevant.

Document actual capabilities and remaining limits. Do not label a mock transport test as a live Telegram verification. Keep secrets and customer-specific settings out of fixtures, screenshots and commits.
