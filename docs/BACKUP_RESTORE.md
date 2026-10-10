# Backup and restore

```bash
./scripts/tacctl backup
./scripts/tacctl verify-backup backups/20261009T200000Z
```

Backup stops API and worker, dumps PostgreSQL in custom format, archives the flat media volume and writes a private manifest with SHA-256 checksums, timestamp and Git commit. An EXIT trap restarts services after the backup attempt. The manifest is recorded in runtime state for `/v1/database/status`. Backups exclude `.env`; store it separately with restricted access. Copy backups off-host and encrypt them using your backup system.

Verification checks the exact expected files, commit syntax, checksums and media archive entries. Links, devices, absolute paths, nested paths and traversal entries are rejected. This detects corruption and dangerous media paths; it is **not a cryptographic signature or proof of trust**. A PostgreSQL dump can execute database instructions during restore: use only backups created by your trusted installation.

Direct operator restore:

```bash
./scripts/tacctl restore backups/TIMESTAMP
```

This requires `RESTORE`, replaces database/media, applies migrations and pauses execution. Running records become uncertain; inspect Telegram and reconcile before resuming. Restoring older data can also resurrect old grant state and lose post-backup audit/operation records. Revoke obsolete credentials and reconcile anything sent since the snapshot. Application idempotency cannot recognize records missing from the restored database.

Direct restore and agent-requested restore now require the backup commit to equal the current checkout commit, matching the conservative rollback policy. This check runs before the confirmation prompt or stopping services. A mismatch blocks recovery even if the revisions might be compatible: review schema/application compatibility in an isolated restore and plan recovery explicitly. `verify-backup` remains an integrity-only check and can inspect snapshots from other revisions; it does not authorize restoring them.

## Agent-requested restore

An agent calls `request_maintenance(action="restore_backup", parameters={"backup_name":"TIMESTAMP"})`. The owner reviews the exact digest within 15 minutes. The execute endpoint returns a fixed `tacctl restore-request REQUEST_ID` command; it never runs a shell. The local operator consumes approval, verifies the archive, records a local one-use receipt and performs the typed restore. A failed/cancelled consumed request requires a fresh approval. Receipts outside the database resist replay when restoring the database itself; they are not protected from the VPS administrator.

Asset deletion follows a separate approved request and refuses files referenced by any operation, workflow or emoji record. File unlink happens after database commit; filesystem failure may leave an orphan for operator cleanup rather than break a referenced record.

See [test evidence](TEST_RESULTS.md). Backup status means the last locally verified snapshot, not that off-site replication or a future restoration is guaranteed.
