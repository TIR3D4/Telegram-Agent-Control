"""Authenticated Streamable HTTP with caller identity preserved into the shared gateway."""

from urllib.parse import urlsplit
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from fastapi import HTTPException
from mcp.server.transport_security import TransportSecuritySettings
from .config import settings
from .security import authenticate
from .gateway import require
from .mcp_server import mcp, caller_credential
from .oauth import challenge


class AuthenticatedMCP:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        token = authorization[7:] if authorization.lower().startswith("bearer ") else ""
        try:
            if not token:
                raise HTTPException(401, "Authentication required")
            who = await run_in_threadpool(authenticate, token)
            if who.human:
                raise HTTPException(
                    403, "Owner credentials are not accepted on MCP; issue a scoped agent grant"
                )
            require(who, "system:read")
        except HTTPException as e:
            await JSONResponse(
                {
                    "error": "invalid_token" if e.status_code == 401 else "insufficient_scope",
                    "detail": e.detail,
                },
                status_code=e.status_code,
                headers={"WWW-Authenticate": challenge()} if e.status_code == 401 else e.headers,
            )(scope, receive, send)
            return
        context = caller_credential.set(token)
        try:
            await self.app(scope, receive, send)
        finally:
            caller_credential.reset(context)


def make_app():
    host = urlsplit(settings().public_url).netloc
    app = mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        max_request_body_size=2 * 1024 * 1024,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[host, "127.0.0.1:*", "localhost:*", "testserver"],
            allowed_origins=[settings().public_url],
        ),
    )
    return AuthenticatedMCP(app)
