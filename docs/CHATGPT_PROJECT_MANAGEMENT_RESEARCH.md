# Managing a software project from ChatGPT

Source inspection: 2026-10-10. The owner clarified that the target includes GitHub code, tests, long-running development tasks and controlled server operations from a ChatGPT conversation, not another chat UI.

## Closest actual projects

| Repository / inspected commit | License | Actual source inspected | Fit and limitations |
|---|---|---|---|
| [escapeWu/chatgpt-web-oauth-mcp](https://github.com/escapeWu/chatgpt-web-oauth-mcp/tree/72bd92af5e09f2d0b6b30c1aed3a922f97a0eead) | MIT, LICENSE read | `tools_git_shell.py`, `pathing.py`, command execution in `shell.py`, OAuth grant/PKCE handling in `oauth.py`; test tree inspected | Closest interaction model: ChatGPT Web inspects/edits files, manages Git/worktrees, runs bounded-output commands and durable jobs, and accesses a persistent Codex runtime. Workspace root is a path anchor, **not a sandbox**: absolute paths are accepted and subprocess execution uses shell=True. OAuth issues authorization-code access tokens without refresh tokens. Useful pattern for a separate development environment, unsuitable on the production Telegram host unchanged. |
| [bestagentkits/cloud-harness-mcp](https://github.com/bestagentkits/cloud-harness-mcp/tree/ad1fffc9993e83c10eb46ef7fe7db6957cb315a1) | MIT, LICENSE read | `apps/api/src/auth.ts`, `apps/runner/src/repository-policy.ts`, `github-app-broker.ts`, GitHub binding service, Git adapter and `compose.yaml` | Most relevant architecture reference: remote workspaces/jobs, principal-scoped GitHub grants and installation tokens, separate API/runner/executor, repository URL/network checks. The runner mounts the Docker socket, so executor hardening does not make the control plane unprivileged. More infrastructure than TAC needs merely to connect ChatGPT. Isolate a development installation from production if adopted. |
| [TAY0123/dockerMCP-ChatGPT](https://github.com/TAY0123/dockerMCP-ChatGPT/tree/f96206f8bcc4569f1bff8d93ffe8fb8bd35eb256) | MIT declared in pyproject; no standalone LICENSE found in inspected tree | `src/docker_mcp_chatgpt/server.py`, `docker-compose.yml`, project metadata | Concrete Docker/Keycloak/Caddy remote coding setup. Exposes arbitrary Bash execution in a root runner container, persistent workspace and GitHub CLI credentials. No host Docker socket found in this compose file. Still too broad for the requested Telegram grant. Keycloak 2 GiB and runner 1 GiB are configured limits, **not measured consumption**. |
| [xyTom/coding-tools-mcp](https://github.com/xyTom/coding-tools-mcp/tree/d7c2dda48bcedbd066c7dbc24a1b63205384d269) | Apache-2.0, LICENSE read | `coding_tools_mcp/server.py` execution/capability sections, `landlock_exec.py`, `docs/mcp-client-config.md` | Lower-level read/search/patch/command tools, permission profiles and optional Linux Landlock confinement, local or OAuth HTTP setup. Isolation depends on the selected profile/platform; some profiles disable Landlock. Useful development-tool building blocks, not a ready Telegram workflow or a solution to account registration. |

These are source observations, not production endorsements. Reference test suites were not executed, services were not deployed, and no credentials were supplied to them. There are no measured RAM/CPU benchmarks here. Pins identify the inspected snapshots; upstream websites may describe later changes.

## The connection boundary still matters

The escapeWu setup explicitly requires an eligible ChatGPT account, developer mode/custom-app registration and workspace approval. Its own documentation says the server cannot control ChatGPT plan or write-action availability. Cloud Harness also documents account registration and distinguishes draft from workspace-published connectors; its mobile limitation statements are the project's documentation, not independent testing of this owner's account.

Official OpenAI [plugin guidance](https://learn.chatgpt.com/docs/plugins) and [quickstart](https://developers.openai.com/plugins/quickstart) were reviewed separately. Do not assume that supporting remote MCP, changing mcp.json, adding OAuth, or enabling a network proxy makes an unavailable account feature available. A real invocation in the owner's phone conversation is required for acceptance.

## Selected architecture for this repository

Keep one conversational surface in ChatGPT and three separate privilege domains:

1. **Telegram:** a narrow connector to the existing REST gateway. Prepare drafts/schedules, inspect status, preserve independent owner approval. Candidate code and tests are in [CHATGPT_CLOUD_CONTROL.md](CHATGPT_CLOUD_CONTROL.md). It is not yet connected in the owner's account.
2. **Development:** use the connected GitHub tools for branches, source, commits and reviewable PRs, with tests in an isolated checkout/CI. The current chat already exposes GitHub tools; there is no reason to duplicate that access inside the Telegram bot. If persistent remote development becomes necessary, evaluate Cloud Harness on a separate worker with repository-scoped credentials. Do not install a root shell tool on the Telegram VPS.
3. **Deployment:** a future fixed-purpose controller can inspect status and prepare a release request for an exact commit. Execution must require independent owner approval, backup, migration compatibility checks, health checks and a report. No arbitrary model command, generic SSH, or automatic database downgrade. The current pinned upgrade script remains the implementation; a remote deployment controller is **not implemented** by this change.

The practical acceptance test is not another installation: connect the private candidate, invoke a read-only tool from the actual ChatGPT conversation, confirm the bound agent identity, and verify iPhone availability. Only after that should a reviewed test-channel publication or server upgrade be proposed. Existing server data, OAuth and secrets remain untouched.

## Current delivery status

- Research and thin Telegram connector candidate: prepared with mocked protocol/security tests and existing gateway/UI regression tests.
- GitHub development: available through this chat's connector; changes remain in a dedicated review branch.
- Live phone-to-Telegram connection: unverified; no successful invocation claimed.
- New remote shell/development service or deployment controller: not installed or exposed.
- Production deployment: not performed, respecting the owner's explicit approval requirement.
