"""Portable remote plugin packaging; cloud registration is a separate host action."""

import io
import json
import re
import zipfile
from urllib.parse import urlsplit


def build_package(public_url, app_id=""):
    parts = urlsplit(public_url)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or parts.path not in {"", "/"}
    ):
        raise ValueError("Use the public HTTPS origin, without credentials, query or path")
    if app_id and not re.fullmatch(r"(?:plugin_)?asdk_app_[0-9a-f]{32}", app_id):
        raise ValueError("Use the registered asdk_app ID shown by ChatGPT, not a plugins_ ZIP ID")
    base = public_url.rstrip("/")
    interface = {
        "displayName": "Telegram Control",
        "shortDescription": "Manage Telegram operations",
        "longDescription": "Use scoped remote Telegram tools. Independent owner approval is required for writes. "
        + (
            "Uses an existing registered ChatGPT connection."
            if app_id
            else "Desktop/CLI MCP bundle. Register a cloud MCP connection for ChatGPT mobile."
        ),
        "category": "Productivity",
        "defaultPrompt": "Inspect Telegram Control capabilities and the current connection before making changes.",
    }
    extension = {"interface": interface}
    files = {}
    if app_id:
        extension["apps"] = "./.app.json"
        files[".app.json"] = {"apps": {"telegram-control": {"id": app_id.removeprefix("plugin_")}}}
    else:
        files["mcp.json"] = {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
            "mcpServers": {"telegram-control": {"type": "streamable-http", "url": base + "/mcp/"}},
        }
    manifest = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "telegram-control",
        "version": "0.3.0",
        "description": "Scoped remote Telegram operations with owner approval",
        "author": {"name": "Telegram Control owner"},
        "extensions": {"com.openai": extension},
    }
    files["plugin.json"] = manifest
    compatibility = {k: v for k, v in manifest.items() if k not in {"$schema", "extensions"}}
    compatibility.update(extension)
    if not app_id:
        compatibility["mcpServers"] = "./.mcp.json"
        files[".mcp.json"] = {"mcpServers": {"telegram-control": {"url": base + "/mcp/"}}}
    files[".codex-plugin/plugin.json"] = compatibility
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr("telegram-control/" + name, json.dumps(value, indent=2) + "\n")
        archive.writestr(
            "telegram-control/README.md",
            "# Telegram Control\n\n"
            + "REST documentation: "
            + base
            + "/agent-guide\n\n"
            + "Never embed credentials in this bundle. A ZIP does not register a ChatGPT cloud connection.\n",
        )
    return data.getvalue()
