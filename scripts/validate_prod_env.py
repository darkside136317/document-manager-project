"""Fail before a production deploy if its environment is incomplete or unsafe."""

from __future__ import annotations

import re
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit


DOMAIN = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]*$")
PORT = re.compile(r"^127\.0\.0\.1:([1-9][0-9]{0,4})$")
BASE_SECRETS = (
    "ADMIN_PASSWORD", "MARIADB_ROOT_PASSWORD", "MEILISEARCH_MASTER_KEY",
    "MINIO_APP_ACCESS_KEY", "MINIO_APP_SECRET_KEY",
)
ROOT_SECRETS = ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD")
BUCKET = re.compile(r"^(?=.{3,63}$)[a-z0-9][a-z0-9.-]*[a-z0-9]$")


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

    data_root = values.get("DATA_ROOT", "")
    if data_root:
        root_path = Path(data_root)
        if not root_path.is_absolute() or root_path == Path("/") or ".." in root_path.parts:
            issues.append("DATA_ROOT must be an absolute host directory outside the source tree")
        elif path.resolve().parents[1] in (root_path.resolve(), *root_path.resolve().parents):
            issues.append("DATA_ROOT must be outside the source tree")
        elif not root_path.is_dir():
            issues.append("Create DATA_ROOT on the host before deployment")

    port = values.get("HTTP_PUBLISH_PORT", "")
    match = PORT.fullmatch(port)
    if not match or int(match.group(1)) > 65535:
        issues.append("HTTP_PUBLISH_PORT must bind to 127.0.0.1:<valid port>")

    mode = values.get("MINIO_MODE", "disabled")
    if mode not in ("disabled", "auto", "manual"):
        issues.append("MINIO_MODE must be disabled, auto, or manual")
    profiles = values.get("COMPOSE_PROFILES", "")
    if profiles != ("auto" if mode == "auto" else ""):
        issues.append("COMPOSE_PROFILES must be auto in auto mode and empty otherwise")
    endpoint = values.get("MINIO_ENDPOINT", "")
    bucket = values.get("MINIO_BUCKET", "")
    if mode == "disabled":
        if endpoint or any(values.get(key) for key in (*ROOT_SECRETS, "MINIO_APP_ACCESS_KEY", "MINIO_APP_SECRET_KEY")):
            issues.append("Leave MinIO endpoint and credentials empty when disabled")
    elif mode == "auto":
        if endpoint != "http://minio:9000" or bucket != "documents":
            issues.append("Auto mode requires MINIO_ENDPOINT=http://minio:9000 and MINIO_BUCKET=documents")
    elif mode == "manual":
        try:
            parsed = urlsplit(endpoint)
            valid_port = parsed.port is None or parsed.port > 0
        except ValueError:
            parsed = urlsplit("")
            valid_port = False
        if (
            parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment or endpoint == "http://minio:9000" or not valid_port
        ):
            issues.append("Manual mode requires the URL of an existing MinIO server in MINIO_ENDPOINT")
        if not BUCKET.fullmatch(bucket) or ".." in bucket or ".-" in bucket or "-." in bucket:
            issues.append("MINIO_BUCKET must be a valid existing bucket name")
        if any(values.get(key) for key in ROOT_SECRETS):
            issues.append("Leave MinIO root credentials empty in manual mode")

    secret_keys = BASE_SECRETS[:3] if mode == "disabled" else BASE_SECRETS + (ROOT_SECRETS if mode == "auto" else ())
    secrets = [values.get(key, "") for key in secret_keys]
    if any(
        len(value) < (8 if mode == "manual" and key.startswith("MINIO_APP_") else 24)
        or "REPLACE" in value or "change_me" in value
        for key, value in zip(secret_keys, secrets)
    ):
        issues.append("Generate strong secrets; existing manual MinIO app keys need at least 8 characters")
    if len(set(secrets)) != len(secrets):
        issues.append("All secrets must be different")

    dev_path = path.with_name(".env.dev")
    if dev_path.exists():
        dev = read_env(dev_path)
        if dev.get("DATA_VOLUME_PREFIX") == prefix:
            issues.append("Production and development must use different data volume prefixes")
        if any(dev.get(key) == values.get(key) for key in secret_keys):
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
