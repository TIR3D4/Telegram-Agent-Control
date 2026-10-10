# v0.4 implementation report

Review branch: `engineering/unified-control-v0.4`, based on `465e256` of `engineering/chatgpt-cloud-control`. Existing dirty local documentation in the prior checkout was preserved using a separate worktree.

Implemented:
- Client-specific connection catalog and secret-free config downloads for REST, MCP, Codex, Claude and ChatGPT.
- Read-only browser connection checks with explicit identity/protocol evidence, no false cloud-connectivity claim.
- Persian responsive operator shell, clearer dashboard, filtered operation cards, visual photo/text composer, independent readable owner review.
- Retained advanced APIs, immutable grants/approval/state-machine behavior and optional legacy chat data.
- Private adapter tools for bounded real-byte media upload and individual nested type retrieval.
- v0.4 branch support in pinned upgrade script; no destructive schema change or new storage system.

Out of scope of completed implementation:
- Host-wide automatic MCP registration when the AI account lacks the feature.
- A host deployment executor/root control exposed to the Telegram agent or web UI.
- Visual forms for every Telegram method or complete translation of every advanced form.
- Live acceptance in all external clients, WebKit on a real iPhone, and production migration verification.

The old draft advertisement remains unchanged on the live service; it was not published as part of engineering tests. No live credentials or user media are included in source. See [architecture and setup](CONTROL_WORKSPACE.md), [test results](V04_TEST_RESULTS.md) and [upgrade procedure](UPGRADE.md).

## Deployed private connector

The existing owner-private Site was updated successfully on 2026-10-10, preserving project/plugin identity, audience and environment revision 1. Site source commit: `41cc4c2a7bba9051a425542f562efe83043da1aa`. Deployment: `appgdep_6ac9f91b65d88191a5a1a31e538e1ff0`, status `succeeded`, `has_mcp=true`. After deployment, the existing plugin's real `inspect_system` call still returned the scoped agent and fresh v0.3 worker status. New tool discovery was not yet refreshed in this conversation, so a live file-byte upload through the new tool is not claimed.

VPS upgrade remains blocked: the actual SSH probe to the specified server returned `Network is unreachable`. The existing Telegram MCP grant has no deployment authority. Run the reviewed pinned upgrade through an authorized server terminal; do not substitute the owner credential or add a generic shell tool. GitHub changes are in PR #4, not merged into the default branch.
