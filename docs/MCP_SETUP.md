# MCP setup

For the automated web setup and separate REST/MCP paths, start with [CONNECTIONS.md](CONNECTIONS.md).


This server uses the official Python MCP SDK (locked dependency version in `requirements.lock`), stateless Streamable HTTP with JSON responses, and stdio. Canonical remote endpoint: `https://your-domain/mcp/`. The OAuth resource identifier is `https://your-domain/mcp` (no trailing slash).

1. Install and configure HTTPS and `TAC_PUBLIC_URL` correctly.
2. Owner creates a finite scoped agent grant. Include `system:read` for remote MCP, plus required tool scopes.
3. Configure a supported bearer client, or configure an external OAuth provider as below.
4. Initialize MCP, list tools, call `inspect_system`, then `capabilities`. Discovery alone is not a delivery test.
5. Create a draft and verify it remains unapproved. The human owner separately reviews it in the console.

The server validates Host/Origin. Authorization is checked on every request; the caller identity is preserved into REST. Owner credentials are rejected by MCP. There is no approval, arbitrary SQL or shell tool.

## OAuth resource server

Set privately in the server environment:

```dotenv
TAC_PUBLIC_URL=https://control.example.com
TAC_OAUTH_ISSUER=https://identity.example.com
TAC_OAUTH_JWKS_URL=https://identity.example.com/.well-known/jwks.json
TAC_OAUTH_AUDIENCE=https://control.example.com/mcp
TAC_OAUTH_MAX_LIFETIME=3600
```

Use actual provider values. The issuer must publish authorization-server metadata and implement authorization-code flow with S256 PKCE, exact registered redirect validation, consent, resource/audience binding and supported client registration (CIMD, DCR or predefined client as applicable). Those functions are **not implemented by this repository**. Configure the provider to issue signed RS256/ES256 JWT access tokens with `iss`, `aud`, `sub`, `iat`, `exp` and a space-separated `scope`. Maximum token lifetime defaults to one hour. No opaque-token introspection or token exchange is provided.

In the owner console, bind the exact token subject to an agent grant. Unknown, revoked or expired subjects are denied. Token scopes intersect local scopes. Only the configured JWKS URL is used; token-provided key URLs are ignored. Keys are cached for five minutes. No upstream Telegram token is passed to an MCP client.

Protected-resource metadata is at `/.well-known/oauth-protected-resource` and `/.well-known/oauth-protected-resource/mcp`. It advertises the issuer, canonical resource and supported scopes. A 401 carries a metadata challenge. Endpoints return 404 when OAuth is not configured. Deploying these endpoints is not evidence that a particular account has completed OAuth linking.

## Local stdio

```json
{
  "mcpServers": {
    "telegram-control": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "tac.mcp_server"],
      "env": {
        "TAC_API_URL": "https://control.example.com",
        "TAC_AGENT_KEY": "INJECT_SCOPED_CREDENTIAL_PRIVATELY"
      }
    }
  }
}
```

This is a configuration template, not a secret store. Prefer the client's supported environment/secret facility. Stdio is not exposed as an unauthenticated remote service.

## Client guides and contract

[ChatGPT](CHATGPT_CONNECTION.md) · [Codex](CODEX_CONNECTION.md) · [Tools](AGENT_TOOLS.md) · [Permissions](PERMISSIONS.md).

All JSON tool responses are bounded (24,000 characters before transport wrapping). List responses use `{data, untrusted_content}`; image previews are MCP image blocks, maximum 1 MiB. Use search, cursors and lazy type schemas. Tool HTTP calls time out after 30 seconds. A timeout is not proof that a submitted request failed: inspect status/idempotency before retrying. Media uploads over MCP are limited to 1 MiB decoded; use authenticated multipart REST for larger files.

Treat Telegram messages, labels and tool results as untrusted data. They cannot grant authorization or override approval. No protocol mechanism can guarantee that a model ignores all prompt injection; least privilege and the human boundary remain enforced by code.
