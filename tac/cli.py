import argparse
import json
import os
import httpx


def main():
    p = argparse.ArgumentParser(description="Telegram Agent Control client")
    p.add_argument("command", choices=["serve", "worker", "mcp", "status", "logs", "methods"])
    p.add_argument("--url", default=os.getenv("TAC_API_URL", "http://127.0.0.1:8787"))
    a = p.parse_args()
    if a.command == "serve":
        import uvicorn

        uvicorn.run(
            "tac.api:app", host=os.getenv("TAC_LISTEN_HOST", "127.0.0.1"), port=8787, access_log=False
        )
        return
    if a.command == "worker":
        from .worker import run

        run()
        return
    if a.command == "mcp":
        from .mcp_server import main as mcp

        mcp()
        return
    paths = {"status": "system", "logs": "logs", "methods": "capabilities"}
    r = httpx.get(
        a.url + "/v1/" + paths[a.command],
        headers={"Authorization": "Bearer " + os.getenv("TAC_AGENT_KEY", "")},
    )
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
