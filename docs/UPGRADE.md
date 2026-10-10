# Upgrade and rollback

Run an upgrade first on a staging copy with no live bot credential. Read the changelog and migration files. Keep a verified pre-upgrade database/media backup and protect `.env` separately.

```bash
./scripts/tacctl doctor
./scripts/tacctl backup
./scripts/tacctl update
```

Version 0.3 uses the backed-up updater described in [CONNECTIONS.md](CONNECTIONS.md).
It accepts the exact known manual OAuth Caddy/ignore changes and preserves other
local edits by stopping for review. It verifies the deployment branch and ancestry,
backs up application data plus provider/configuration, builds and migrates, then
leaves execution paused. Existing grants and provider identities are preserved.

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

## Reviewed mobile assistant upgrade

See [one-command pinned upgrade](MOBILE_ASSISTANT.md#installation--upgrade). Existing password/OAuth provisioning is retained without repeat prompts. `--commit` pins the reviewed revision; failures retain a private upgrade report and backups. Cross-revision DB rollback is blocked pending an isolated compatibility review.

## v0.4 workspace candidate

Use `engineering/unified-control-v0.4` and an exact reviewed commit with `scripts/upgrade.py`. Read the target script from the fetched commit before running, because an older installation does not recognize this branch. Run inside `/opt/Telegram-Agent-Control`. Preserve `.env` and OAuth overrides; never re-run first-install to upgrade. No new schema revision is introduced. Execution stays paused until the owner reviews and resumes in the dashboard. The separately hosted ChatGPT adapter requires its own reviewed deployment. A successful local test is not proof of a successful VPS upgrade.
