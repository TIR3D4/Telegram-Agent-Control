#!/usr/bin/env python3
"""Build a secret-free remote bundle; pass only an existing registered App ID."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tac.plugin_package import build_package  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--app-id", default="", help="Existing registered asdk_app ID (not the ZIP plugin ID)"
    )
    parser.add_argument("--output", default="data/telegram-control.zip")
    args = parser.parse_args()
    data = build_package(args.url, args.app_id)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print("Bundle saved: " + str(target))
    if not args.app_id:
        print(
            "Desktop/CLI bundle. Register a remote MCP connection in ChatGPT before packaging a mobile-capable App mapping."
        )


if __name__ == "__main__":
    main()
