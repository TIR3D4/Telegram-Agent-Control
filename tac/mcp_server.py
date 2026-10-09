"""MCP adapter over the same authenticated REST API. Owner approval is never exposed."""

import os
import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

mcp = MCPServer(
    "Telegram Agent Control",
    instructions="Discover methods, inspect their schemas, validate, then submit. Writes are drafts until the owner approves. Read operations run in the durable worker. Poll operation status. Never claim success from submission alone.",
)


def call(verb, path, body=None, params=None):
    base = os.environ.get("TAC_API_URL", "http://127.0.0.1:8787").rstrip("/")
    from .config import settings

    key = os.environ.get("TAC_AGENT_KEY") or settings().agent_key.get_secret_value()
    with httpx.Client(timeout=60, headers={"Authorization": "Bearer " + key}) as client:
        r = client.request(verb, base + path, json=body, params=params)
        r.raise_for_status()
        return r.json()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def capabilities(query: str = "") -> dict:
    """Search every method in the pinned Telegram Bot API version."""
    return call("GET", "/v1/capabilities", params={"q": query})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def method_schema(method: str) -> dict:
    """Read complete nested input schema and official constraints before constructing a request."""
    return call("GET", "/v1/methods/" + method)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def validate_request(method: str, payload: dict) -> dict:
    return call("POST", "/v1/validate", {"method": method, "payload": payload})


@mcp.tool()
def submit_operation(
    method: str,
    payload: dict,
    idempotency_key: str,
    attachments: dict | None = None,
    run_at: str | None = None,
) -> dict:
    """Queue reads or create a write draft; run_at is an ISO timestamp with timezone. Does not grant approval."""
    return call(
        "POST",
        "/v1/operations",
        {
            "method": method,
            "payload": payload,
            "idempotency_key": idempotency_key,
            "attachments": attachments or {},
            "run_at": run_at,
        },
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def operation_status(operation_id: str) -> dict:
    return call("GET", "/v1/operations/" + operation_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def inspect_system() -> dict:
    return call("GET", "/v1/system")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def inspect_database() -> dict:
    """Read table schema and row counts without arbitrary SQL or secret exposure."""
    return call("GET", "/v1/database/overview")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def inspect_logs(after: int = 0, operation_id: str = "") -> list:
    return call(
        "GET",
        "/v1/logs",
        params={"after": after, "resource_id": operation_id} if operation_id else {"after": after},
    )


@mcp.tool()
def create_automation(
    name: str, steps: list, trigger: dict, timezone: str = "Asia/Tehran", max_runs: int = 1
) -> dict:
    """Create a workflow draft; owner approves the exact content/trigger/count before any run."""
    return call("POST", "/v1/workflows", locals())


@mcp.tool()
def cancel_operation(operation_id: str) -> dict:
    return call("POST", "/v1/operations/" + operation_id + "/cancel")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def search_emoji(query: str = "", pack: str = "", offset: int = 0) -> list:
    return call("GET", "/v1/emojis", params={"q": query, "pack": pack, "offset": offset})


@mcp.tool()
def prepare_emoji_preview(emoji_id: str) -> dict:
    """Download original and render visual preview. Inspect the image using emoji_image before labeling."""
    return call("POST", "/v1/emojis/" + emoji_id + "/preview")


@mcp.tool()
def label_emoji(
    emoji_id: str, description: str, tags: list[str], style: str = "", reviewed: bool = False
) -> dict:
    return call(
        "PATCH",
        "/v1/emojis/" + emoji_id,
        {"description": description, "tags": tags, "style": style, "reviewed": reviewed},
    )


@mcp.tool()
def bind_emoji(role: str, emoji_id: str) -> dict:
    return call("PUT", "/v1/emoji-roles/" + role, {"emoji_id": emoji_id})


@mcp.resource("tac://guide")
def guide() -> str:
    return "Read capabilities → method_schema → validate_request → submit_operation → owner approval → operation_status. Use inspect_logs for diagnostics. Never retry an uncertain write without reconciliation. Import emoji with getStickerSet, then view preview before labeling."


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def emoji_image(asset_id: str):
    """Return the actual PNG/WebP preview as an MCP image content block for visual selection."""
    import base64
    from mcp.types import ImageContent

    base = os.environ.get("TAC_API_URL", "http://127.0.0.1:8787").rstrip("/")
    r = httpx.get(
        base + "/v1/assets/" + asset_id,
        headers={
            "Authorization": "Bearer "
            + (
                os.environ.get("TAC_AGENT_KEY")
                or __import__("tac.config", fromlist=["settings"]).settings().agent_key.get_secret_value()
            )
        },
        timeout=30,
    )
    r.raise_for_status()
    mime = r.headers.get("content-type", "").split(";")[0]
    if mime not in ("image/png", "image/webp", "image/jpeg"):
        raise ValueError("Choose a rendered image preview asset")
    return ImageContent(type="image", mimeType=mime, data=base64.b64encode(r.content).decode())


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
