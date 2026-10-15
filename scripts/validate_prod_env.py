"""Fail before a production deploy if its environment is incomplete or unsafe."""

from __future__ import annotations

import re
import stat
import sys
from pathlib import Path


DOMAIN = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]*$")
PORT = re.compile(r"^127\.0\.0\.1:([1-9][0-9]{0,4})$")
SECRETS = ("ADMIN_PASSWORD", "MARIADB_ROOT_PASSWORD", "MEILISEARCH_MASTER_KEY")


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Line {number} has no '='")
        key, value = line.split("=", 1)
        if key in values:
            raise ValueError(f"Duplicate variable: {key}")
        values[key] = value
    return values


def validate(path: Path) -> list[str]:
    issues = []
    if not path.is_file():
        return [f"Missing {path}; copy docker/.env.prod.example first"]
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        issues.append("Environment file must be readable only by its owner (chmod 600)")
    try:
        values = read_env(path)
    except ValueError as exc:
        return issues + [str(exc)]

    domain = values.get("FRAPPE_SITE_NAME", "").lower()
    if not DOMAIN.fullmatch(domain) or domain in ("example.com", "example.net", "example.org") or domain.endswith(
        (".example.com", ".example.net", ".example.org", ".local", ".localhost")
    ):
        issues.append("FRAPPE_SITE_NAME must be the customer's real DNS hostname")
    if values.get("PUBLIC_URL") != f"https://{domain}":
        issues.append("PUBLIC_URL must be https:// followed by FRAPPE_SITE_NAME")

    prefix = values.get("DATA_VOLUME_PREFIX", "")
    project = values.get("COMPOSE_PROJECT_NAME", "")
    if not IDENTIFIER.fullmatch(prefix) or prefix in ("docmanager", "docmanager_customer"):
        issues.append("DATA_VOLUME_PREFIX must uniquely identify this customer deployment")
    if not IDENTIFIER.fullmatch(project) or project in ("docker", "docmanager_customer"):
        issues.append("COMPOSE_PROJECT_NAME must uniquely identify this customer deployment")

    port = values.get("HTTP_PUBLISH_PORT", "")
    match = PORT.fullmatch(port)
    if not match or int(match.group(1)) > 65535:
        issues.append("HTTP_PUBLISH_PORT must bind to 127.0.0.1:<valid port>")

    secrets = [values.get(key, "") for key in SECRETS]
    if any(len(value) < 24 or "REPLACE" in value or "change_me" in value for value in secrets):
        issues.append("Generate independent random values of at least 24 characters for all three secrets")
    if len(set(secrets)) != len(secrets):
        issues.append("The three secrets must be different")

    dev_path = path.with_name(".env.dev")
    if dev_path.exists():
        dev = read_env(dev_path)
        if dev.get("DATA_VOLUME_PREFIX") == prefix:
            issues.append("Production and development must use different data volume prefixes")
        if any(dev.get(key) == values.get(key) for key in SECRETS):
            issues.append("Production must not reuse development secrets")
    return issues


if __name__ == "__main__":
    env_path = Path(sys.argv[1] if len(sys.argv) > 1 else "docker/.env.prod")
    problems = validate(env_path)
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        sys.exit(1)
    print(f"Production environment is ready: {env_path}")
