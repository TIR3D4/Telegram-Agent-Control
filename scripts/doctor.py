#!/usr/bin/env python3
"""One-command Compose diagnosis. Reports never include raw subprocess output."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def command(args, timeout=20, stdin=None):
    return subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=timeout, cwd=ROOT)


def collect(agent=False, telegram=True):
    checks = []

    def add(name, status, message, hint=""):
        checks.append(dict(name=name, status=status, message=message, hint=hint))
        if sys.stderr.isatty():
            print(f"[{status}] {name}", file=sys.stderr, flush=True)

    def check(name, action, hint):
        start = time.monotonic()
        try:
            status, message = action()
            add(name, status, message, hint if status != "PASS" else "")
        except Exception:
            add(name, "FAIL", "Probe failed or timed out; raw output omitted.", hint)
        checks[-1]["duration_ms"] = round((time.monotonic() - start) * 1000)

    def revision():
        result = command(["git", "rev-parse", "HEAD"])
        sha = result.stdout.strip()
        if result.returncode or not re.fullmatch(r"[a-f0-9]{40}", sha):
            raise ValueError("Unknown revision")
        return "PASS", "Checkout commit: " + sha

    check("checkout", revision, "Run doctor from the installed repository.")

    def disk():
        free = shutil.disk_usage(ROOT).free
        return "PASS" if free >= 2 * 1024**3 else "WARN", f"Host filesystem free: {free // 1024**2} MiB."

    check("host.disk", disk, "Review disk usage; do not delete database volumes.")
    add(
        "host.reboot",
        "WARN" if Path("/var/run/reboot-required").exists() else "PASS",
        "System reboot required."
        if Path("/var/run/reboot-required").exists()
        else "No reboot-required marker.",
        "Schedule any required reboot separately; doctor never reboots.",
    )

    def env_permissions():
        files = [p for p in [ROOT / ".env", ROOT / ".oauth.env", ROOT / ".oauth-db.env"] if p.exists()]
        if not files:
            return "FAIL", "Installation environment file missing."
        unsafe = any(p.is_symlink() or p.stat().st_mode & 0o077 for p in files)
        return (
            ("WARN", "Some secret configuration files allow group/other access or are symlinks.")
            if unsafe
            else ("PASS", "Secret configuration file permissions are private.")
        )

    check(
        "host.secret_permissions",
        env_permissions,
        "Review ownership and set secret configuration files to mode 0600.",
    )

    def compose_config():
        result = command(["docker", "compose", "config", "--quiet"])
        return (
            ("PASS", "Compose configuration valid.")
            if result.returncode == 0
            else ("FAIL", "Compose configuration invalid.")
        )

    check(
        "compose.configuration",
        compose_config,
        "Inspect Docker/Compose installation and configuration locally.",
    )

    def services():
        result = command(["docker", "compose", "ps", "--all", "--format", "json"])
        if result.returncode:
            raise ValueError("Compose inaccessible")
        raw = result.stdout.strip()
        rows = json.loads(raw) if raw.startswith("[") else [json.loads(line) for line in raw.splitlines()]
        present = {row["Service"]: row for row in rows}
        bad = []
        for name in ("api", "worker", "postgres"):
            row = present.get(name, {})
            if row.get("State") != "running" or row.get("Health") in {"unhealthy", "starting"}:
                bad.append(name)
        for name in ("oauth", "oauth-db", "caddy"):
            row = present.get(name)
            if row and (row.get("State") != "running" or row.get("Health") in {"unhealthy", "starting"}):
                bad.append(name)
        migrate = present.get("migrate")
        if migrate and (migrate.get("State") != "exited" or int(migrate.get("ExitCode", -1)) != 0):
            bad.append("migrate")
        return (
            ("FAIL", "Services requiring attention: " + ", ".join(bad))
            if bad
            else ("PASS", "Required services running; observed optional services and migration healthy.")
        )

    check(
        "compose.services",
        services,
        "Inspect service status; doctor does not start, stop or restart containers.",
    )

    def backup():
        candidates = sorted((ROOT / "backups").glob("[0-9]*T[0-9]*Z/manifest.json"))
        if not candidates:
            return "WARN", "No backup manifest found."
        result = command(
            [sys.executable, str(ROOT / "scripts/backup_manifest.py"), "verify", str(candidates[-1].parent)],
            timeout=60,
        )
        if result.returncode:
            return "FAIL", "Latest backup checksum/archive verification failed."
        age = (datetime.now(timezone.utc).timestamp() - candidates[-1].stat().st_mtime) / 86400
        return (
            "WARN" if age > 7 else "PASS",
            f"Latest backup checksum/archive verified; manifest age {max(0, int(age))} days. Restore not exercised.",
        )

    check(
        "backup.integrity",
        backup,
        "Create/verify a backup; prove restoration in an isolated environment, not production.",
    )
    if sys.stderr.isatty():
        print(
            "Checking application, public routes and Telegram (bounded timeouts)...",
            file=sys.stderr,
            flush=True,
        )
    token = getpass.getpass("Scoped agent credential (hidden, not saved): ") if agent else ""
    try:
        result = command(
            ["docker", "compose", "exec", "-T", "api", "python", "-m", "tac.doctor"],
            timeout=420,
            stdin=json.dumps({"credential": token, "telegram": telegram}),
        )
        if result.returncode:
            raise ValueError("Container diagnostics failed")
        data = json.loads(result.stdout)
        checks.extend(data["checks"])
    except Exception:
        add(
            "application.probes",
            "FAIL",
            "Application diagnostics unavailable or timed out; raw output omitted.",
            "Check that API is running with an image containing tac.doctor, then rerun.",
        )
    return {"format": 1, "created_at": datetime.now(timezone.utc).isoformat(), "checks": checks}


def summarize(report):
    counts = Counter(row["status"] for row in report["checks"])
    code = 1 if counts["FAIL"] else 2 if counts["WARN"] or counts["SKIP"] else 0
    report["summary"] = {status: counts[status] for status in ("PASS", "WARN", "FAIL", "SKIP")}
    report["exit_code"] = code
    return code


def render(report):
    lines = ["Telegram Agent Control — installation diagnosis", report["created_at"], ""]
    for row in report["checks"]:
        lines.append(f"[{row['status']:4}] {row['name']}: {row['message']}")
        if row.get("hint") and row["status"] != "PASS":
            lines.append("       Next: " + row["hint"])
    lines += [
        "",
        "Summary: " + " | ".join(f"{k}={v}" for k, v in report["summary"].items()),
        "Exit: " + str(report["exit_code"]),
        "No publications, approvals, migrations, restarts or automatic repairs performed.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Prompt privately for an existing scoped agent credential; test MCP tool call and approval denial",
    )
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram read-only network probes")
    parser.add_argument("--json", action="store_true", help="Print machine-readable report")
    args = parser.parse_args()
    os.umask(0o077)
    report = collect(args.agent, not args.no_telegram)
    code = summarize(report)
    directory = ROOT / "diagnostics"
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for suffix, content in [("json", json.dumps(report, indent=2)), ("txt", render(report))]:
        with (directory / (stamp + "." + suffix)).open("x") as stream:
            stream.write(content)
    print(json.dumps(report) if args.json else render(report), end="\n")
    if not args.json:
        print("Private reports: diagnostics/" + stamp + ".{txt,json}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
