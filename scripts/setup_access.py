#!/usr/bin/env python3
"""Idempotent console + managed OAuth setup. Secrets stay off stdout/command lines."""

import getpass
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("passwords", ROOT / "tac/passwords.py")
passwords = importlib.util.module_from_spec(spec)
spec.loader.exec_module(passwords)


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def read_env(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if v.startswith('"'):
            v = json.loads(v)
        elif v.startswith("'") and v.endswith("'"):
            v = v[1:-1]
        values[k.strip()] = v
    return values


def write_env(path, changes):
    path = Path(path)
    old = path.read_text() if path.exists() else ""
    lines = [line for line in old.splitlines() if line.split("=", 1)[0].strip() not in changes]
    # Escape Compose's interpolation marker in password hashes and other values.
    lines.extend(k + "=" + json.dumps(str(v).replace("$", "$$")) for k, v in changes.items())
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    path.chmod(0o600)


def prompt(label):
    # Also works when the one-command updater was piped to python.
    # Buffered read/write mode (r+) requires seeking on newer Python versions.
    # A terminal is not seekable: use independent text streams instead.
    try:
        with open("/dev/tty", "w") as output:
            output.write(label)
            output.flush()
        with open("/dev/tty", "r") as terminal:
            value = terminal.readline()
    except OSError:
        raise SystemExit(
            "Interactive terminal required. Run bash scripts/tacctl setup in your SSH terminal."
        ) from None
    if not value:
        raise SystemExit("Setup cancelled")
    return value.strip()


def account():
    env = read_env(".env")
    if env.get("TAC_OWNER_PASSWORD_HASH") and "--password" not in sys.argv:
        return env, None
    username = prompt("Console username (use your existing OAuth username if present): ")
    if not username or len(username) > 120:
        raise SystemExit("Username must be 1–120 characters")
    password = getpass.getpass("Console / OAuth password (12+ characters; hidden): ")
    if len(password) < 12 or len(password) > 1024:
        raise SystemExit("Password must be 12–1024 characters")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords did not match")
    # Persist only after the provider user has been created/verified.
    env.update(TAC_OWNER_USERNAME=username, TAC_OWNER_PASSWORD_HASH=passwords.hash_password(password))
    return env, password


def request(url, method="GET", payload=None, token=None, form=False):
    headers = {}
    data = None
    if payload is not None:
        data = (urllib.parse.urlencode(payload) if form else json.dumps(payload)).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    # Provider URL comes only from the operator's protected configuration.
    with urllib.request.urlopen(req, timeout=20) as response:  # nosec B310
        body = response.read()
        return json.loads(body) if body else None


def wait_for(url, seconds=240):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            return request(url)
        except (urllib.error.URLError, TimeoutError):
            time.sleep(3)
    raise SystemExit("OAuth is not ready yet. Existing data is preserved; rerun scripts/tacctl setup.")


def prepare_provider(env):
    """Preserve the previously installed override and provider database."""
    override = Path("compose.override.yaml")
    base = env["TAC_PUBLIC_URL"].rstrip("/")
    if not override.exists():
        override.write_text((ROOT / "deploy/compose.oauth.yaml").read_text())
    else:
        # Inspect service names without rendering any env values.
        services = subprocess.check_output(["docker", "compose", "config", "--services"], text=True).split()
        if "oauth" not in services or "oauth-db" not in services:
            raise SystemExit(
                "Existing compose.override.yaml has custom services; add deploy/compose.oauth.yaml before setup."
            )
    if not Path(".oauth.env").exists() and not Path(".oauth-db.env").exists():
        db_password = secrets.token_urlsafe(36)
        write_env(
            ".oauth-db.env",
            {"POSTGRES_DB": "keycloak", "POSTGRES_USER": "keycloak", "POSTGRES_PASSWORD": db_password},
        )
        write_env(
            ".oauth.env",
            {
                "KC_DB": "postgres",
                "KC_DB_URL": "jdbc:postgresql://oauth-db:5432/keycloak",
                "KC_DB_USERNAME": "keycloak",
                "KC_DB_PASSWORD": db_password,
                "KC_BOOTSTRAP_ADMIN_USERNAME": "tac-admin",
                "KC_BOOTSTRAP_ADMIN_PASSWORD": secrets.token_urlsafe(36),
                "KC_HOSTNAME": base + "/auth",
                "KC_HTTP_RELATIVE_PATH": "/auth",
                "KC_HTTP_ENABLED": "true",
                "KC_PROXY_HEADERS": "xforwarded",
                "KC_HEALTH_ENABLED": "true",
            },
        )
    if not Path(".oauth.env").exists() or not Path(".oauth-db.env").exists():
        raise SystemExit(
            "Incomplete OAuth secret files; restore the missing file from backup. Nothing regenerated."
        )
    run("docker", "compose", "up", "-d", "oauth-db", "oauth")
    path = Path("Caddyfile")
    old = path.read_text()
    if "oauth:8080" not in old:
        marker = "    reverse_proxy api:8787"
        if old.count(marker) != 1:
            raise SystemExit("Custom Caddyfile: add the /auth route from docs/CONNECTIONS.md")
        path.write_text(
            old.replace(
                marker,
                """    @oauth path /auth /auth/*
    handle @oauth {
        reverse_proxy oauth:8080
    }
    handle {
        reverse_proxy api:8787
    }""",
            )
        )
    run("docker", "compose", "up", "-d", "caddy")
    try:
        for action in ("validate", "reload"):
            run(
                "docker",
                "compose",
                "exec",
                "-T",
                "caddy",
                "caddy",
                action,
                "--config",
                "/etc/caddy/Caddyfile",
                "--adapter",
                "caddyfile",
            )
    except subprocess.CalledProcessError:
        path.write_text(old)
        raise
    return base


def provision(env, password):
    base = prepare_provider(env)
    issuer = base + "/auth/realms/telegram-control"
    metadata = wait_for(base + "/auth/realms/master/.well-known/openid-configuration")
    if metadata["issuer"] != base + "/auth/realms/master":
        raise SystemExit("Issuer mismatch; verify the public domain")
    if password is None and all(
        env.get(k) for k in ("TAC_OAUTH_ADMIN_CLIENT_SECRET", "TAC_OWNER_OAUTH_SUBJECT")
    ):
        request(
            issuer + "/protocol/openid-connect/token",
            "POST",
            {
                "grant_type": "client_credentials",
                "client_id": env.get("TAC_OAUTH_ADMIN_CLIENT_ID", "tac-console"),
                "client_secret": env["TAC_OAUTH_ADMIN_CLIENT_SECRET"].replace("$$", "$"),
            },
            form=True,
        )
        return {}
    provider = read_env(".oauth.env")
    auth = request(
        base + "/auth/realms/master/protocol/openid-connect/token",
        "POST",
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": provider["KC_BOOTSTRAP_ADMIN_USERNAME"],
            "password": provider["KC_BOOTSTRAP_ADMIN_PASSWORD"].replace("$$", "$"),
        },
        form=True,
    )
    token = auth["access_token"]
    admin = base + "/auth/admin/realms/telegram-control"

    def kc(path="", method="GET", body=None):
        return request(admin + path, method, body, token)

    try:
        kc()
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        request(
            base + "/auth/admin/realms",
            "POST",
            {
                "realm": "telegram-control",
                "enabled": True,
                "displayName": "Telegram Control",
                "sslRequired": "external",
                "registrationAllowed": False,
                "bruteForceProtected": True,
                "accessTokenLifespan": 300,
            },
            token,
        )
    # This private realm uses username/password; do not force an unrelated email enrollment.
    profile = kc("/users/profile")
    changed = False
    for attribute in profile.get("attributes", []):
        if attribute.get("name") == "email" and "required" in attribute:
            attribute.pop("required")
            changed = True
    if changed:
        kc("/users/profile", "PUT", profile)
    username = env["TAC_OWNER_USERNAME"]
    users = kc("/users?" + urllib.parse.urlencode({"username": username, "exact": "true"}))
    if not users:
        if password is None:
            raise SystemExit(
                "OAuth user missing. Use scripts/tacctl setup --password to choose a shared login once."
            )
        kc(
            "/users",
            "POST",
            {
                "username": username,
                "enabled": True,
                "firstName": username,
                "lastName": "Owner",
                "credentials": [{"type": "password", "value": password, "temporary": False}],
            },
        )
        users = kc("/users?" + urllib.parse.urlencode({"username": username, "exact": "true"}))
    if len(users) != 1:
        raise SystemExit("Unexpected OAuth user lookup")
    subject = users[0]["id"]
    if password is not None:
        # Explicit operator setup synchronizes the existing login too; subject and grants stay intact.
        kc(
            "/users/" + subject + "/reset-password",
            "PUT",
            {"type": "password", "value": password, "temporary": False},
        )
    # Client scopes must appear in the signed scope claim. No elevated Telegram admin scope by default.
    scopes = [
        "system:read",
        "telegram:read",
        "posts:read",
        "media:read",
        "workflows:read",
        "emoji:read",
        "logs:read",
        "metrics:read",
        "database:read",
        "settings:read",
        "posts:write",
        "media:write",
        "keyboards:write",
        "workflows:write",
        "emoji:write",
        "maintenance:request",
    ]
    existing = {s["name"]: s for s in kc("/client-scopes")}
    for name in ["tac-agent"] + scopes:
        if name not in existing:
            scope = {
                "name": name,
                "protocol": "openid-connect",
                "attributes": {"include.in.token.scope": "true"},
            }
            if name == "tac-agent":
                scope["protocolMappers"] = [
                    {
                        "name": "tac-resource",
                        "protocol": "openid-connect",
                        "protocolMapper": "oidc-audience-mapper",
                        "config": {
                            "included.custom.audience": base + "/mcp",
                            "id.token.claim": "false",
                            "access.token.claim": "true",
                        },
                    }
                ]
            kc("/client-scopes", "POST", scope)
    # Dedicated realm service account for web client creation. It cannot administer other realms.
    clients = kc("/clients?clientId=tac-console")
    if not clients:
        kc(
            "/clients",
            "POST",
            {
                "clientId": "tac-console",
                "enabled": True,
                "protocol": "openid-connect",
                "publicClient": False,
                "serviceAccountsEnabled": True,
                "standardFlowEnabled": False,
                "directAccessGrantsEnabled": False,
                "fullScopeAllowed": False,
            },
        )
        clients = kc("/clients?clientId=tac-console")
    cid = clients[0]["id"]
    service = kc("/clients/" + cid + "/service-account-user")["id"]
    management = kc("/clients?clientId=realm-management")[0]["id"]
    roles = [kc("/clients/" + management + "/roles/" + r) for r in ("manage-clients", "view-clients")]
    kc("/users/" + service + "/role-mappings/clients/" + management, "POST", roles)
    kc("/clients/" + cid + "/scope-mappings/clients/" + management, "POST", roles)
    secret = kc("/clients/" + cid + "/client-secret")["value"]
    return {
        "TAC_OAUTH_ISSUER": issuer,
        "TAC_OAUTH_JWKS_URL": issuer + "/protocol/openid-connect/certs",
        "TAC_OAUTH_AUDIENCE": base + "/mcp",
        "TAC_OAUTH_MAX_LIFETIME": "3600",
        "TAC_OAUTH_ADMIN_CLIENT_ID": "tac-console",
        "TAC_OAUTH_ADMIN_CLIENT_SECRET": secret,
        "TAC_OWNER_OAUTH_SUBJECT": subject,
    }


def main():
    os.chdir(ROOT)
    env, password = account()
    changes = {}
    public = env.get("TAC_PUBLIC_URL", "").rstrip("/")
    external = (
        env.get("TAC_OAUTH_ISSUER") and env["TAC_OAUTH_ISSUER"] != public + "/auth/realms/telegram-control"
    )
    if external:
        print("External OAuth provider configuration preserved; console login configured separately.")
    elif public.startswith("https://"):
        changes.update(provision(env, password))
    if password is not None:
        changes.update(
            TAC_OWNER_USERNAME=env["TAC_OWNER_USERNAME"],
            TAC_OWNER_PASSWORD_HASH=env["TAC_OWNER_PASSWORD_HASH"],
        )
    if changes:
        write_env(".env", changes)
    run("docker", "compose", "up", "-d", "--no-deps", "api", "worker")
    for attempt in range(40):
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "api", "curl", "-fsS", "http://localhost:8787/health/ready"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            break
        time.sleep(3)
    else:
        raise SystemExit("API not ready after configuration. Rerun setup once the service is healthy.")
    if not external:
        run("docker", "compose", "exec", "-T", "api", "python", "-m", "tac.access_setup")
    # Existing expired/revoked grants are never silently renewed.
    print("Setup complete. Sign in at " + env["TAC_PUBLIC_URL"] + " and open Connect an AI.")
    print("Use Agent permissions to create API keys or an OAuth grant. Existing grants remain unchanged.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f"OAuth setup stopped: HTTP {e.code}. Secrets and databases are preserved; rerun setup after correcting provider access."
        ) from None
    except (urllib.error.URLError, subprocess.CalledProcessError):
        raise SystemExit(
            "Setup stopped. Existing configuration is preserved. Check service status, then rerun scripts/tacctl setup."
        ) from None
