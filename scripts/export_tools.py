#!/usr/bin/env python3
"""Export the actual MCP discovery contract. Contains no runtime secrets."""

import asyncio
import json
from pathlib import Path
from tac.mcp_server import mcp


async def main():
    tools = await mcp.list_tools()
    content = {"format": 1, "tools": [t.model_dump(by_alias=True, exclude_none=True) for t in tools]}
    Path("docs/agent-tools.schema.json").write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
    print(f"Exported {len(tools)} actual tool schemas")


if __name__ == "__main__":
    asyncio.run(main())
