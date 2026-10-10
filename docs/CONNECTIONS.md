# One setup, two ways to connect

The responsive web console works in phone and desktop browsers. The server has no
Windows requirement. REST and MCP are independent clients of the same policy and
operation state machine. A ChatGPT plugin's availability is controlled by ChatGPT;
a ZIP installation marked **Desktop only** does not prove a cloud MCP connection
has been registered.

## Install once

Run `bash scripts/install.sh` from a checked-out repository. The installer requests
bot/channel/domain configuration, then a console username and password once. With
a public HTTPS domain it also generates provider secrets, starts PostgreSQL and
Keycloak, waits for bootstrap, routes `/auth`, provisions the realm, login user,
audience, scopes and a realm-scoped OAuth client-management service account. A new
setup also creates one 90-day OPERATE grant for that login; an existing subject
grant is preserved even if expired/revoked.

Login passwords are PBKDF2-SHA256 hashed, never printed. Provider secrets are
stored with mode 0600 and excluded from Git and Docker builds. The same initial
username/password is used in the console and the provider login page. API agents
receive a separate scoped key; never give them the owner login or recovery key.
No-domain installs offer console + bearer REST/MCP locally; public OAuth needs HTTPS.
Docker + Compose v2 and DNS pointing to the server are prerequisites. The included
installer offers the official Docker installation flow if Docker is absent.

## Upgrade existing installations

From the repository directory, use `bash scripts/tacctl update`. To adopt the new
updater on an old release, fetch the deployment branch and run its upgrade script:

```bash
git fetch origin engineering/production-hardening-v0.2 && git show FETCH_HEAD:scripts/upgrade.py | python3 -
```

The updater verifies the branch and fast-forward ancestry, backs up application
DB/media, OAuth DB and protected configuration, and preserves the known manual
OAuth Caddy route. It accepts only the exact known Caddy/ignore-file customization;
unrelated tracked edits are preserved and require review. Existing provider
volumes, realm subjects, grants and secrets are reused. It builds, migrates, waits
for readiness, and asks for the username/password only if console login is not
configured. On the first adoption, use the existing OAuth username; the chosen
password is synchronized to that provider user without changing its subject.
Subsequent upgrades don't regenerate passwords or renew grants.

Execution is paused during upgrade and remains paused after it. Sign in, review
pending/uncertain operations and resume from the console. A failed upgrade reports
the step and retains backups; it never resets volumes or attempts an unsafe
automatic schema downgrade. See INSTALL.md for application data recovery. Protected
`backups/upgrade-*/oauth.dump` and configuration copies are separate from the app
backup and must be retained together for full provider recovery. Do not restore
only an OAuth dump without the matching configuration and a reviewed recovery plan.

To finish an interrupted setup: `bash scripts/tacctl setup`.
If the initial v0.3 updater stopped with `io.UnsupportedOperation: File or stream is not seekable`
at the username prompt, run `git pull --ff-only origin engineering/production-hardening-v0.2`
then `bash scripts/tacctl setup`. The host-side prompt fix needs no image rebuild;
already completed backups, migrations and running services are retained. To explicitly change
both the local and provider login: `bash scripts/tacctl setup --password` (requires
provider setup-admin access). Old console sessions are invalidated by a changed
password hash. Routine browser logout invalidates the current session.

## REST mode: no plugin required

1. Open your HTTPS domain on the phone and sign in.
2. Open **Connect an AI → Create API key**.
3. Choose permitted channels, actions, expiry and quotas; review and create.
4. Save the returned `tac_...` credential once. It is hashed in the database.
5. Copy the API URL and agent instructions into an AI client that actually supports
   outbound HTTP execution, and supply the credential in that client's secret store.

Links are shown in the console:

- `/v1` — REST base URL; use `Authorization: Bearer <scoped key>`.
- `/agent-guide` — public machine-readable usage instructions, no secrets.
- `/openapi.json` — live OpenAPI contract.
- `/docs` — interactive API reference.

Giving a URL to an AI that has only browsing/chat cannot enable arbitrary HTTP
writes. A draft is not a sent message: approve it independently in the web console.

## MCP mode: remote Streamable HTTP

Use `https://YOUR-DOMAIN/mcp/`. Bearer-capable MCP clients can use the same scoped
API key as REST. Nothing runs on the phone or Windows machine. OAuth clients use
Authorization Code + PKCE S256; password and implicit grants are disabled on the
new AI clients. Access tokens carry the canonical `/mcp` audience and explicit
scopes; the server intersects them with an active local grant for the user's subject.

For an OAuth client:

1. In the AI host choose **Add custom MCP server** and enter the remote URL.
2. Copy the **exact callback URL shown by that host** into the console's
   **Connect an AI → Create OAuth connection** form. No wildcard callback is accepted.
3. Paste the generated client ID and secret into the host's OAuth form.
4. In **Agent permissions**, inspect the initial OAuth grant for the setup account.
   The subject is prefilled by **Manage OAuth permissions** for installations needing a grant;
   setup never revives expired or revoked grants. A subject is bound to one grant.
5. Complete provider login using your setup account and consent. Test a read-only
   capability call before testing an owner-approved Telegram draft.

### ChatGPT mobile and plugin packaging

An uploaded `mcp.json` remote-server entry can still be treated as a desktop plugin.
The documented cloud path is to register **Add custom MCP server** in ChatGPT. The
result has a technical ID starting with `plugin_asdk_app`. An existing plugin can
then map that **verified registered ID** in `.app.json` via
`extensions.com.openai.apps`. Never put a URL or an invented ID in this mapping.
The UI/account must expose this registration feature; server code cannot remove
host account restrictions or guarantee mobile availability.

You can download the cloud bundle from **Connect an AI → Plugin package**, without
using the terminal. Alternatively, use `python3 scripts/package_plugin.py --url https://YOUR-DOMAIN --app-id VERIFIED_ID`
to build a portable plugin bundle for an existing registered connection. Without
`--app-id`, the bundle is for MCP-capable desktop/CLI hosts and explicitly says so.
Importing a ZIP does not itself register the remote server in ChatGPT.

Official references:
- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/plugins/build/auth
- https://learn.chatgpt.com/docs/plugins

## Custom reverse proxies

Preserve the `/auth` prefix when forwarding to Keycloak. Caddy example:

```caddyfile
@oauth path /auth /auth/*
handle @oauth {
    reverse_proxy oauth:8080
}
handle {
    reverse_proxy api:8787
}
```

No provider/database ports are exposed to the internet; Caddy terminates TLS.
For external identity providers instead of managed Keycloak, configure the existing
issuer/JWKS/audience variables and maintain clients/users at that provider. Do not
run the managed setup against an unrelated provider.

## No custom-MCP registration / mobile-only owner

For control **inside ChatGPT**, see the [cloud connector candidate and activation gates](CHATGPT_CLOUD_CONTROL.md). It is not connected until a real plugin call succeeds. The [independent console assistant](MOBILE_ASSISTANT.md) is optional and is a different chat surface; it does not satisfy in-ChatGPT control. No manifest or network workaround is claimed to unlock a missing host feature.
