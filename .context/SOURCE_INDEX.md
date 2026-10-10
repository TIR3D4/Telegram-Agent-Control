# Task-oriented source index

Read only the relevant row, then its dependencies/tests.

| Task | Sources | Tests/docs |
|---|---|---|
| Auth/approvals | tac/security.py, gateway.py, oauth.py, operations.py | tests/test_governance.py, test_oauth_mcp.py; docs/PERMISSIONS.md |
| REST/MCP clients | tac/api.py, control_api.py, mcp_server.py, remote_mcp.py, connection_profiles.py | tests/test_control_protocol.py, test_connection_profiles.py; docs/CONTROL_WORKSPACE.md |
| Worker/schedules | tac/worker.py, workflows.py, db.py | locate worker/workflow tests with rg; docs/ARCHITECTURE.md |
| Media/emoji | tac/media.py, telegram.py | locate media/emoji tests; docs/EMOJI.md |
| Console | tac/static/workspace.js, workspace.css, app.js, control.js | tests/ui/workspace.spec.js, console.spec.js |
| Private ChatGPT bridge | integrations/chatgpt-cloud/lib/connector.mjs and app/ | integrations/chatgpt-cloud/tests/; README.md in that subtree |
| Installation/diagnosis | scripts/tacctl, upgrade.py, doctor.py; tac/doctor.py | tests/test_doctor.py, test_mobile_operations.py; docs/DIAGNOSTICS.md |
| Migrations/recovery | migrations/, tac/maintenance.py, scripts/backup_manifest.py, rollback.py | docs/BACKUP_RESTORE.md; isolated CI only |
| CI gates | .github/workflows/ci.yml, requirements.lock, package.json | docs/TESTING.md; historical run linked in handoff |

Avoid bulk-reading tac/data/, screenshots, lockfiles, logs, backups, sessions or dependencies. Generated schemas must remain accessible when the current task needs them. No Atlas map has been generated; this is a curated source index, not an Atlas output.
