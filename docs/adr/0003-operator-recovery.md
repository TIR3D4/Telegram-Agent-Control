# ADR 0003 — Operator-controlled recovery

Accepted for v0.2. Agents may inspect safe database metadata and request a restore, but cannot execute arbitrary SQL/shell. A finite exact-parameter human approval returns a fixed operator command. The local CLI consumes consent, verifies a trusted snapshot and requires typed confirmation. Filesystem receipts prevent simple replay after restoring the database.

Checksums detect corruption, not malicious backup authors. Rollback restores matching code/data and pauses execution. Test evidence currently covers same-revision mechanics, not arbitrary downgrade compatibility. Retain backup/config secrets outside source control and keep production rollout separate from implementation approval.
