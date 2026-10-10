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
