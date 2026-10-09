# Permissions and independent approval

An effective agent policy is the intersection of its role preset, explicit scopes, exact method list, allowed destinations and the installation allowlist. OAuth additionally intersects scopes consented in the access token. Roles do not override missing grants. IDs belong to their creator; another agent receives 404. The human owner can inspect all records.

| Preset | Intended access | Cannot do |
|---|---|---|
| READ | System, authorized updates, own operations/media/workflows, emoji catalog, logs, metrics, safe DB/config inspection | Create writes, change catalog, approve |
| OPERATE | READ plus post drafts, media, keyboards, workflows, emoji labeling and maintenance requests | Arbitrary bot administration, change its policy, approve or execute maintenance |
| ADMIN | OPERATE plus explicitly granted `telegram:admin` methods | Act as the human owner, issue credentials, approve itself, shell/SQL |

Scopes: `system:read`, `telegram:read`, `posts:read`, `posts:write`, `media:read`, `media:write`, `keyboards:write`, `workflows:read`, `workflows:write`, `emoji:read`, `emoji:write`, `logs:read`, `metrics:read`, `database:read`, `settings:read`, `maintenance:request`, `telegram:admin`.

Ordinary default methods are limited to selected get/send/edit/delete/pin/copy/forward methods in `tac/gateway.py`. Discovery filters by method grant; discovery does not authorize execution. Numeric chat IDs and usernames are distinct policy entries: add both only if needed. Source chats in forwarding/copying are checked too. Inline message IDs and callback-query answers without a verified destination are owner-only in this release.

## Credential lifecycle

Owner console → Agent permissions → choose name, scope, methods, destinations, expiry, request/minute and operation/day quotas → review exact grant → create. A local `tac_` credential is returned once and stored only as a SHA-256 digest. It has cryptographic random entropy; this is not password hashing. Lifetime is at most 365 days. A grant can instead bind an external OAuth `sub` and receive no local key.

Rotation/revocation uses a maintenance request, exact digest confirmation by the owner and single-use execution. An agent may request changes only to its own credential. Revocation also stops queued execution. Rotating a key preserves the identity and its resources. Changing scopes/channels is not a mutable agent API; issue a reviewed replacement grant and revoke the old one. Existing assets are not automatically transferred between identities.

Fresh interactive installs disable legacy shared agent/reader keys with `TAC_LEGACY_AGENT_KEYS_ENABLED=false`. For upgrades, the setting defaults to true for compatibility: migrate agents to finite grants, then explicitly disable it. Legacy keys have no expiry or per-agent quota and should not be used for a public production integration. The bootstrap owner key remains a powerful operator secret; keep it out of agents and MCP (MCP rejects it). Rotate that key locally and restart, using the operator's change process.

## Consent and effects

Every external Telegram write requires human approval, including bulk deletion, broadcasts, admin changes and post edits. Approval covers exact parameters and time, expires, and is revoked on revision. Default expiry is one hour after the scheduled execution, within a 30-day maximum horizon. Workflow approval defaults to seven days (same maximum horizon), bounded by `max_runs` and allowed steps. Agents cannot call an approval tool.

Maintenance approvals expire after 15 minutes and cover exact parameters. Supported changes: agent rotation/revocation, deletion of unreferenced assets, execution pause/resume and restore requests. Restore remains an operator action with a verified backup and typed confirmation. Configuration/secret changes and bot-account removal are operator-managed; there is no unrestricted remote configuration endpoint.

Quotas are atomic database buckets. MCP authentication and its downstream REST request each consume a request unit. Daily operation quotas count new operation records, including workflow children; idempotent replays do not consume additional operation units. Default grant limits are 120 requests/minute and 500 operations/day; the console deliberately starts the daily field at 100.

The shared emoji catalog is installation-wide. Agents with emoji access can inspect it and permitted editors can label it. Do not treat it as a private per-agent asset store. Database inspection exposes safe schema/count metadata, not unrestricted row content or SQL.
