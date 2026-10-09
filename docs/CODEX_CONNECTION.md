# Connect Codex

For Codex clients supporting remote MCP bearer configuration, create a finite scoped credential in the TAC owner console and provide it through an environment variable.

```toml
[mcp_servers.telegram_control]
url = "https://control.example.com/mcp/"
bearer_token_env_var = "TAC_SCOPED_AGENT_KEY"
```

Set `TAC_SCOPED_AGENT_KEY` privately in the process environment that starts your client. Do not put the value in the repository, TOML example or shell history. The variable name above is a client-side choice; it is not the legacy server bootstrap key. Use the configuration location and supported fields for your installed Codex client.

For OAuth, configure the external provider and subject grant first, add the HTTP server, then use the client's documented MCP login flow (CLI: `codex mcp login telegram_control`). Do not configure both a static bearer secret and OAuth for the same test and assume which identity won. Current documented registration options include CIMD/DCR; provider compatibility still needs a live test.

Verify `inspect_system` returns the expected `agent:<id>` and scopes. Verify a forbidden destination fails. Create a draft, inspect status and let the human owner approve separately. Codex approval settings cannot bypass TAC approval. [Tool contract](AGENT_TOOLS.md) and [stdio alternative](MCP_SETUP.md).

Official source checked 2026-10-09: [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). Automated tests exercise the actual MCP protocol and shared REST behavior; a live Codex account/provider login is not included in that evidence.
