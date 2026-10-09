# Connecting an agent

## REST

Give the agent the installation URL and its **agent key** through your client's secret configuration. It can discover methods, inspect schema, prepare requests, monitor operations and query logs. Keep the owner key separate. The agent cannot approve its own writes.

## MCP over stdio

Install the package in a Python 3.12 environment, then use your MCP client's configuration:

```json
{
  "mcpServers": {
    "telegram-control": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "tac.mcp_server"],
      "env": {
        "TAC_API_URL": "https://your-domain",
        "TAC_AGENT_KEY": "SET_IN_CLIENT_SECRET_STORAGE"
      }
    }
  }
}
```

## Remote MCP

Streamable HTTP endpoint: `https://your-domain/mcp/`. Send `Authorization: Bearer <agent-key>`. The service checks the host against `TAC_PUBLIC_URL`; configure that correctly before connecting. Use a client supporting a custom bearer header. Clients requiring OAuth discovery cannot connect directly to this API-key mode; an OAuth integration is a separate deployment step, not an automatic property of hosting an MCP endpoint.

Tools: capability search, method schema, validation, operation submission/status/cancellation, system/database/log inspection, workflow creation, emoji search/preview/image/label/binding. Full Bot API methods are reached through `submit_operation`, rather than loading 185 schemas into every model turn.

Suggested agent instruction:

> Discover the relevant method and read its schema. Validate a complete payload, then submit with a stable idempotency key. Writes remain drafts for owner review. Poll the operation before claiming delivery. If the result is uncertain, inspect logs and ask the owner to reconcile; do not resend. For emoji, inspect actual image previews before labeling or binding a role. Never disclose secrets.

## What runs on the VPS

The API, MCP transport, scheduler and worker run continuously. Cron/event workflows and delayed steps do not depend on an open chat. This release supplies the tools for external agents; it does not run a model by itself or include model API credits.
