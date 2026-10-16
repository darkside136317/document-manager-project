"""Run the production Compose stack with its optional MinIO overlay."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from validate_prod_env import read_env, validate


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/prod_compose.py <docker compose arguments>", file=sys.stderr)
        return 2

    docker_dir = Path(__file__).resolve().parents[1] / "docker"
    env_path = docker_dir / ".env.prod"
    if not env_path.is_file():
        print(f"Missing {env_path}; copy .env.prod.example first", file=sys.stderr)
        return 2
    try:
        values = read_env(env_path)
    except ValueError as exc:
        print(f"Invalid production environment: {exc}", file=sys.stderr)
        return 2
    problems = validate(env_path)
    if problems:
        for problem in problems:
            print(f"Invalid production environment: {problem}", file=sys.stderr)
        return 2
    mode = values.get("MINIO_MODE", "disabled")
    if mode not in ("disabled", "auto", "manual"):
        print("MINIO_MODE must be disabled, auto, or manual", file=sys.stderr)
        return 2

    command = [
        "docker", "compose", "--env-file", str(env_path),
        "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml",
    ]
    if mode != "disabled":
        command.extend(["-f", "docker-compose.prod.minio.yml"])
    command.extend(sys.argv[1:])
    # File values win over unrelated shell variables, including COMPOSE_PROFILES.
    environment = os.environ.copy()
    environment.update(values)
    environment["COMPOSE_PROFILES"] = values.get("COMPOSE_PROFILES", "")
    return subprocess.run(command, cwd=docker_dir, env=environment, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
