# Upgrade and rollback

Run an upgrade first on a staging copy with no live bot credential. Read the changelog and migration files. Keep a verified pre-upgrade database/media backup and protect `.env` separately.

```bash
./scripts/tacctl doctor
./scripts/tacctl backup
./scripts/tacctl update
```

`update` refuses tracked local modifications, makes a backup, fast-forwards the current tracked branch, builds, stops API/worker, applies Alembic migrations and starts with execution **paused**. It does not merge divergent branches or deploy from model-generated commands. A build failure leaves the old running installation intact; a migration failure leaves execution stopped for operator investigation. Inspect logs and schema revision before resuming from the owner console.

For an existing v0.1 installation, back up using the old version before checking out the v0.2 branch. Once the new source is checked out, stop API/worker, build and run `docker compose run --rm migrate`, then `docker compose run --rm --no-deps -T api python -m tac.maintenance pause-upgrade`, then `docker compose up -d`. Do not switch binaries while old workers are still processing.

## v0.2 migration behavior

Revisions `3ad7b764f596` and `9906fa12eb62` add finite grants/quotas/maintenance requests, resource ownership, approval expiry and audit/operation correlation. Existing assets/workflows/runs default to owner ownership; they are not silently shared with newly issued agents. Existing approvals without expiry fail closed and require review. Existing bootstrap agent keys remain compatible until explicitly disabled; issue scoped replacements and set `TAC_LEGACY_AGENT_KEYS_ENABLED=false`.

## Rollback

```bash
./scripts/tacctl verify-backup backups/TIMESTAMP
./scripts/tacctl rollback backups/TIMESTAMP
```

Rollback requires a clean tracked tree and a locally available Git commit matching the manifest. After `ROLLBACK`, it backs up the current installation, stops execution, checks out the recorded commit detached, builds and restores the matching database/media. Execution remains paused. Do not run newer-schema data with older code. A detached checkout does not have an update tracking branch: explicitly choose the intended branch before the next update.

The automated Compose drill tests the mechanics against the same revision. Cross-release rollback to an arbitrary historic image/migration has **not** been verified; test the exact versions and protect data before use. Pre-v0.2 backups lack manifests and are not accepted by the new restore command. Restore them using their original version's documented operator procedure in isolation; do not manufacture a manifest for an untrusted archive.
