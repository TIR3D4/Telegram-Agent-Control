"""Authenticated Streamable HTTP MCP. The REST API remains the authority."""

import hmac
from urllib.parse import urlsplit
from starlette.responses import JSONResponse
from mcp.server.transport_security import TransportSecuritySettings
from .config import settings
from .mcp_server import mcp


class AuthenticatedMCP:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            auth = headers.get(b"authorization", b"").decode()
            expected = "Bearer " + settings().agent_key.get_secret_value()
            if not settings().agent_key.get_secret_value() or not hmac.compare_digest(auth, expected):
                await JSONResponse({"error": "Valid agent bearer key required"}, status_code=401)(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)


def make_app():
    host = urlsplit(settings().public_url).netloc
    app = mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[host, "127.0.0.1:*", "localhost:*", "testserver"],
            allowed_origins=[settings().public_url],
        ),
    )
    return AuthenticatedMCP(app)
