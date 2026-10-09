#!/usr/bin/env python3
"""Operator-only rollback to the code commit recorded with a verified backup."""

import subprocess
import sys
from pathlib import Path
from backup_manifest import verify


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    root = Path(__file__).resolve().parent.parent
    directory = Path(sys.argv[1]).resolve()
    meta = verify(directory)
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root).strip():
        raise SystemExit("Commit/stash tracked changes first")
    run("git", "cat-file", "-e", meta["commit"] + "^{commit}")
    if input("Restore code, database and media from this backup? Type ROLLBACK: ") != "ROLLBACK":
        raise SystemExit("Cancelled")
    # Backup current installation before leaving the current code revision.
    run("./scripts/tacctl", "backup")
    run("docker", "compose", "stop", "api", "worker")
    run("git", "checkout", "--detach", meta["commit"])
    run("docker", "compose", "build")
    run("./scripts/tacctl", "restore", str(directory), input="RESTORE\n", text=True)
    print("Rollback complete. Execution remains paused; inspect the recorded state before resuming.")


if __name__ == "__main__":
    main()
