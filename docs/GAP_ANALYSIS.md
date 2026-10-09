# Baseline audit (v0.1)

Baseline: `faf2b9d73f7c687a2ad2cfd07bdac92f605941fb`. Existing passing CI is evidence for those tests only.

| Area | Baseline | Gap / priority |
|---|---|---|
| Bot transport | Functional: JSON/multipart, 185 pinned method contracts | Most live method semantics untested; no MTProto or account sessions |
| Queue/scheduler | Functional: PostgreSQL claim locks, leases, uncertain results | P0: execution must recheck revoked principals and expiring approval; bound retries |
| Approval | Functional: hash binds exact payload/media/time | P0: expiry and separate human identity; workflow approval revision race |
| REST access | Three shared static keys | P0: per-agent credentials, expiry/revocation, scopes and row ownership |
| MCP | SDK Streamable HTTP + stdio | P0: shared backend credential collapses caller identity; no OAuth resource metadata; incomplete tool surface |
| Media | Upload and immutable asset IDs | P1: ownership, metadata/list/reuse/delete and reference safety |
| Keyboard | Selected schema/semantic validation | P1: builder/preview and first-class tools |
| Logs | Persistent operation audit + JSON process logs | P1: correlation, denied access, metrics, retention, request tracing |
| Database | Migrations, introspection, backup scripts | P1: migration/status/backup evidence and controlled maintenance requests |
| Workflows | Bounded cron/once/update with frozen steps | P1: owner/agent policy lifecycle, expiry and quotas |
| UI | Functional responsive JSON editor, operation approvals, emoji catalog | P1: scoped credentials, channels/media/keyboard/diagnostics views |
| Installer | Compose install/update/restore/uninstall tested | P1: rollback compatibility, credential lifecycle, backup checksums, no false success |
| QA | 400 PG tests + 2 browser tests, many registry/transport parameterizations | P0/P1: auth isolation, OAuth, protocol calls, fault/recovery, scans and type checks |

Code review is targeted. A comprehensive penetration test, load benchmark, live Telegram acceptance and client-account OAuth linking are separate gates.
