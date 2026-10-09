# Operations and recovery

Current detailed procedures: [upgrade/rollback](UPGRADE.md), [verified backup/restore](BACKUP_RESTORE.md), [observability](OBSERVABILITY.md).

## Persistence

PostgreSQL stores operations and their approved hash, schedules/workflow definitions, occurrences, audit events, received Telegram updates, asset metadata, emoji labels and role bindings. Media files live in a separate volume and are referenced by immutable asset IDs. Alembic versions schema changes.

Production claims rely on PostgreSQL row locking with `SKIP LOCKED`. SQLite is a single-worker development option. Each claimed operation receives a fencing token. A stale worker cannot overwrite the result recorded after lease recovery. Expired write leases become uncertain, not automatically resent.

## Inspection and logs

Application logs are JSON to stdout. Compose rotates API/worker logs at 10 MB with five files. Use `tacctl logs` for HTTP requests and errors, or the log collection of your choice. Persistent audit events are exposed by `/v1/logs` with ID cursor and action/resource filters. Operation errors and outcomes have their own records. `/v1/system` reports worker heartbeat, queue counts and pause state. `/v1/database/overview` provides schema and table counts.

The audit API has no update/delete endpoint. This is application-level append-only behavior, not a tamper-proof or cryptographically signed ledger; a PostgreSQL administrator can alter records. HTTP request audit retention is bounded by the configured window; domain evidence remains retained. See [observability](OBSERVABILITY.md). Monitor disk growth before enabling large event feeds.

Secrets are loaded from environment and redacted from responses/logs. `.env` and backups are local private files. Sensitive Telegram content can still be present in database payloads and media: use encrypted VPS disks/backups where needed and limit access to the server. The service does not promise application-level encryption of every record.

## Backup and restore

```bash
./scripts/tacctl backup
./scripts/tacctl restore backups/20261010T120000Z
```

Backup stops API/worker, creates a PostgreSQL custom-format dump and media archive, then restarts services. Backups exclude `.env`; protect it separately. Copy backups to a separate machine and verify restoration. Backup files are not committed to Git.

Restore requires typed confirmation, replaces the database/media and sets execution paused. Running operations in the snapshot become uncertain. Review operations against Telegram before resuming. Only restore archives created by this trusted installation; restore is an administrator action, not an agent endpoint.

## Updating / uninstalling

`update` requires a clean tracked working tree, creates a backup, fast-forwards the checkout, builds the new image, stops workers, runs migrations and starts services. If a migration fails, keep execution stopped, inspect the error and restore the preceding backup if necessary. Never downgrade code against a newer schema without an explicit migration/restore plan.

`uninstall` removes containers/network while preserving volumes, `.env` and backups. `purge` separately requires `DELETE` and removes volumes. It deliberately leaves backups and `.env` for the operator to handle.

## Troubleshooting

| Symptom | Check |
|---|---|
| Draft never runs | Owner approval and matching content digest |
| Queued work is late | Worker heartbeat, pause state, run_at timezone, Telegram rate limit |
| `uncertain` | Telegram channel and audit; reconcile before retrying |
| Telegram 403 | Bot membership and the specific administrator permission |
| Target rejected | Exact numeric ID or username in `TAC_ALLOWED_CHATS` |
| Invalid Host on MCP | `TAC_PUBLIC_URL` matches the actual domain |
| Blank emoji preview | Inspect original animation; first frame may be transparent |
| Database authentication failure | Existing role password must match both URL and Compose password |

Internal request/worker failures also create persistent audit events when the database is available. During a database outage, use the structured container logs. API request logs omit bodies and authorization headers.
