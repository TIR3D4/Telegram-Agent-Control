#!/usr/bin/env python3
"""One-command, backed-up upgrade, including adoption of the manual OAuth setup.

Run from the repository root. This script uses only the Python standard library,
so it can be read from the fetched revision before the installed code is upgraded.
"""

import argparse
import json
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

BRANCH = "engineering/production-hardening-v0.2"
ALLOWED_BRANCHES = {BRANCH, "engineering/mobile-assistant"}
REPORT = {}
REPORT_PATH = None
CONFIG_FILES = (".env", ".oauth.env", ".oauth-db.env", "compose.override.yaml", "Caddyfile", ".dockerignore")


def run(*args, **kwargs):
    REPORT["step"] = " ".join(str(x) for x in args[:3])
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


def wait_worker(since):
    script = (
        "from tac.db import Session,RuntimeState; from datetime import datetime; "
        "s=Session(); r=s.get(RuntimeState,'worker'); "
        "assert r and datetime.fromisoformat(r.value['heartbeat']).timestamp() >= " + repr(since)
    )
    for attempt in range(20):
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "api", "python", "-c", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return
        time.sleep(2)
    raise SystemExit("Worker heartbeat failed after restart; execution remains paused and backups retained")


def main():
    global REPORT_PATH
    parser = argparse.ArgumentParser(description="Pinned, backed-up operator upgrade; no agent shell")
    parser.add_argument("--branch", choices=sorted(ALLOWED_BRANCHES))
    parser.add_argument("--commit", help="Exact reviewed 40-character commit; must be on the fetched branch")
    args = parser.parse_args()
    if not Path("compose.yaml").exists() or not Path(".git").exists():
        raise SystemExit("Run this command inside the Telegram-Agent-Control checkout")
    current_branch = output("git", "branch", "--show-current")
    branch = args.branch or current_branch
    if current_branch not in ALLOWED_BRANCHES:
        raise SystemExit("Unexpected deployment branch; no files changed")
    if args.commit and not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        raise SystemExit("Expected a complete commit SHA")
    if output("git", "diff", "--name-only", "--cached"):
        raise SystemExit("Staged changes found; preserve/review them before upgrading")
    run("git", "fetch", "origin", branch)
    fetched = output("git", "rev-parse", "FETCH_HEAD")
    target = args.commit or fetched
    run("git", "merge-base", "--is-ancestor", target, fetched)
    REPORT.update(
        target_commit=target,
        branch=branch,
        status="running",
        previous_commit=output("git", "rev-parse", "HEAD"),
    )
    print("Reviewed upgrade target: " + target, flush=True)
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
    REPORT_PATH = directory / "upgrade-report.json"
    REPORT["backup_directory"] = str(directory)
    save_report()
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
        if branch != current_branch:
            local = subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/heads/" + branch])
            if local.returncode == 0:
                run("git", "merge-base", "--is-ancestor", branch, target)
                run("git", "switch", branch)
            else:
                run("git", "switch", "-c", branch)
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
    run("docker", "compose", "run", "--rm", "--no-deps", "-T", "api", "alembic", "heads")
    run("docker", "compose", "run", "--rm", "migrate")
    restarted_at = time.time()
    run("docker", "compose", "up", "-d")
    wait_ready()
    wait_worker(restarted_at)
    # Preserve existing login and OAuth clients. First-time console setup needs no new identity service.
    from_env = Path(".env").read_text()
    if not any(
        line.startswith("TAC_OWNER_PASSWORD_HASH=") and line.split("=", 1)[1].strip().strip("\"'")
        for line in from_env.splitlines()
    ):
        run(sys.executable, "scripts/setup_access.py", "--console-only")
    wait_ready()
    run("bash", "scripts/tacctl", "doctor")
    REPORT["status"] = "succeeded"
    save_report()
    print(
        "Upgrade complete. Sign in to the web console; execution stays PAUSED until you review and resume it."
    )


def save_report():
    if REPORT_PATH:
        REPORT_PATH.write_text(json.dumps(REPORT, indent=2) + "\n")
        REPORT_PATH.chmod(0o600)


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, SystemExit, OSError) as error:
        REPORT["status"] = "failed"
        REPORT["error_type"] = type(error).__name__
        save_report()
        if isinstance(error, SystemExit):
            raise
        raise SystemExit(
            "Upgrade stopped at a failed step. Backups/configuration are retained. Do not reset the database; inspect service status and rerun."
        ) from None
