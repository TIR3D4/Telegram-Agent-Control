# Connect ChatGPT

Status: resource-server authentication and protocol behavior are covered by automated tests. **No live ChatGPT account linking has been completed for this release.** Account/workspace permissions, available connector/app UI and tool behavior depend on the current client.

1. Provide a publicly reachable HTTPS `/mcp/` endpoint with a valid certificate. A cloud client cannot reach your VPS's localhost or SSH tunnel.
2. Configure the external OAuth provider and subject-bound grant in [MCP setup](MCP_SETUP.md). Do not assume a custom bearer header available in another MCP client is supported in ChatGPT's connection UI.
3. In the supported custom app/MCP connection flow for your account, enter the endpoint and required OAuth client details. Use the exact callback URL shown by the current UI/documentation; register it exactly at the provider. Do not guess callback URLs or use wildcard redirect registration.
4. Complete provider authorization. Confirm that the token has the canonical resource audience and maps to the intended least-privilege grant.
5. Ask for `inspect_system` and a small `capabilities` result. Then create a draft and confirm in the owner console that it did not publish.
6. Test an explicitly approved post in a test channel before any production workflow.

The platform's tool confirmation is additional to TAC's owner approval; it does not automatically approve a post in TAC. This server exposes no owner-approval tool. Models may not inspect every animation frame from a single returned image; use rendered previews and original files appropriately.

Official references checked 2026-10-09: [OpenAI authentication](https://developers.openai.com/plugins/build/auth), [MCP authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization), [MCP security](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices). OAuth login/PKCE/client registration are supplied by the external authorization server, not by TAC. See [known limitations](KNOWN_LIMITATIONS.md).
