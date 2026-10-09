# Security model

TAC is a trusted, single-operator control plane with scoped external agents. It is not a hostile-tenant hosting platform. Protect the owner account/key, VPS, database and OAuth issuer. Read [permissions](PERMISSIONS.md) for exact enforcement.

## Enforced boundaries

- HTTPS for remote access; localhost host binding by default; PostgreSQL is not exposed.
- Finite hashed agent credentials or externally signed subject-mapped OAuth JWTs; exact issuer/audience/expiry/signing algorithms; token-provided key URLs ignored.
- Role, scope, method and channel intersection; foreign resource IDs denied; current grant/approval rechecked before worker claim.
- Human owner outside MCP; expiring digest-bound consent for every Telegram write and destructive maintenance. Agents cannot approve or expand their policy.
- JSON/MCP byte limits, immutable file IDs, no user-controlled filesystem path, no arbitrary shell or SQL endpoint.
- Redaction of configured keys, bot token patterns, local agent keys, JWTs and sensitive dictionary fields. Safe schema/config diagnostics never return secrets.
- Media archive verification rejects path traversal and links. Restore only from trusted local snapshots.
- Prompt-injection content remains data, while authority is enforced in services rather than model instructions.

## Threats and remaining trust

A stolen owner key is equivalent to the owner. It is a local bootstrap credential, not MFA. Grant creation/permission escalation requires a human-authenticated request but cannot prove a physical human typed it; never delegate that key to software agents. Fresh installs disable legacy shared agent keys; upgrading operators must disable them after migrating credentials.

Telegram content, post bodies and files are stored in database/media and backups. Redaction protects logs/responses against known secret forms; it cannot recognize every arbitrary confidential string embedded in prose. No field-level database encryption or encrypted backup implementation is included. Use restricted access and encrypted storage/off-site backups.

MIME metadata is supplied by the uploader; this is not antivirus scanning or universal media decoding validation. Emoji rendering runs constrained-time subprocesses under the non-root application user, but not in a dedicated hostile-file sandbox. Only grant media/catalog writes to trusted agents and monitor resources.

The configured OAuth issuer/JWKS/telemetry endpoint is operator-trusted. External IdP login, client registration, redirect validation, PKCE, revocation and consent must be configured there. Local grant revocation is immediate for future authentication/claims; an in-flight upstream request cannot be recalled. No arbitrary token passthrough to third-party services.

Rate limits apply to scoped authenticated grants; unauthenticated traffic and connection limits require reverse-proxy/firewall controls. The fixed single-bot adapter has no MTProto sessions. Bot tokens are configured on the server, not returned to agents. An operation payload may legitimately contain a webhook secret and is stored privately; never publish database dumps.

The audit store is not cryptographically immutable. Backups restore older grant/audit state and require reconciliation. Exactly-once sending across network loss or old snapshots is impossible to guarantee here.

## Verification and reporting

See [test evidence](TEST_RESULTS.md). Static analysis, dependency audit and automated boundary tests do not constitute an independent penetration test or production certification. Report vulnerabilities through GitHub private reporting when enabled, otherwise contact the repository owner privately. Never include live credentials or exploitable production data in a public issue.
