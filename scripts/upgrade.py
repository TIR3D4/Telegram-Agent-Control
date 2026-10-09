#!/usr/bin/env python3
"""One-command, backed-up upgrade, including adoption of the manual OAuth setup.

Run from the repository root. This script uses only the Python standard library,
so it can be read from the fetched revision before the installed code is upgraded.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

BRANCH = "engineering/production-hardening-v0.2"
CONFIG_FILES = (".env", ".oauth.env", ".oauth-db.env", "compose.override.yaml", "Caddyfile", ".dockerignore")


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def managed_change(name, old, current):
    """Only adopt the exact known manual migration. Never discard unrelated edits."""
    if name == ".dockerignore":
        return set(old.splitlines()) <= set(current.splitlines()) and set(current.splitlines()) - set(
            old.splitlines()
        ) <= {".oauth*.env", "data/", ""}
    if name == "Caddyfile":
        marker = "    reverse_proxy api:8787"
        replacement = """    @oauth path /auth /auth/*
    handle @oauth {
        reverse_proxy oauth:8080
    }
    handle {
        reverse_proxy api:8787
    }"""
        return old.count(marker) == 1 and current == old.replace(marker, replacement)
    return False


def wait_ready():
    for attempt in range(40):
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "api", "curl", "-fsS", "http://localhost:8787/health/ready"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return
        time.sleep(3)
    raise SystemExit(
        "API readiness failed. Execution remains paused. Inspect docker compose logs api; backup retained."
    )


def main():
    if not Path("compose.yaml").exists() or not Path(".git").exists():
        raise SystemExit("Run this command inside the Telegram-Agent-Control checkout")
    if output("git", "branch", "--show-current") != BRANCH:
        raise SystemExit("Unexpected deployment branch; no files changed")
    if output("git", "diff", "--name-only", "--cached"):
        raise SystemExit("Staged changes found; preserve/review them before upgrading")
    run("git", "fetch", "origin", BRANCH)
    target = output("git", "rev-parse", "FETCH_HEAD")
    run("git", "merge-base", "--is-ancestor", "HEAD", target)
    dirty = output("git", "diff", "--name-only").splitlines()
    saved = {}
    for name in dirty:
        old = output("git", "show", "HEAD:" + name) + "\n"
        current = Path(name).read_text()
        if not managed_change(name, old, current):
            raise SystemExit(
                "Unrecognized local change preserved: " + name + ". Commit or review it before upgrading."
            )
        saved[name] = current
    directory = Path("backups") / ("upgrade-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    directory.mkdir(parents=True, mode=0o700)
    directory.chmod(0o700)
    (directory / "previous-commit").write_text(output("git", "rev-parse", "HEAD") + "\n")
    for name in CONFIG_FILES:
        if Path(name).exists():
            shutil.copy2(name, directory / name)
            (directory / name).chmod(0o600)
    # Full app data backup before code or schema changes. Existing routine handles in-flight operations.
    run("bash", "scripts/tacctl", "backup")
    services = output("docker", "compose", "config", "--services").splitlines()
    if "oauth-db" in services:
        fd = os.open(directory / "oauth.dump", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            run(
                "docker",
                "compose",
                "exec",
                "-T",
                "oauth-db",
                "pg_dump",
                "-U",
                "keycloak",
                "-d",
                "keycloak",
                "-Fc",
                stdout=f,
            )
    if dirty:
        run("git", "restore", "--", *dirty)
    merged = False
    try:
        run("git", "merge", "--ff-only", target)
        merged = True
    finally:
        # Restore the live reverse proxy route; ignore patterns are supplied by the new revision.
        for name, content in saved.items():
            if name == "Caddyfile" or not merged:
                Path(name).write_text(content)
    print("Protected upgrade backup: " + str(directory), flush=True)
    run("docker", "compose", "build")
    run("docker", "compose", "stop", "api", "worker")
    run(
        "docker",
        "compose",
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "api",
        "python",
        "-m",
        "tac.maintenance",
        "pause-upgrade",
    )
    run("docker", "compose", "run", "--rm", "migrate")
    run("docker", "compose", "up", "-d")
    wait_ready()
    run(sys.executable, "scripts/setup_access.py")
    wait_ready()
    run("bash", "scripts/tacctl", "doctor")
    print(
        "Upgrade complete. Sign in to the web console; execution stays PAUSED until you review and resume it."
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        raise SystemExit(
            "Upgrade stopped at a failed step. Backups/configuration are retained. Do not reset the database; inspect service status and rerun."
        ) from None
