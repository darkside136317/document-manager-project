#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root/docker"

if [[ ! -f .env.dev ]]; then
  echo "Thiếu docker/.env.dev. Tạo từ docker/.env.dev.example rồi điền cấu hình dev." >&2
  exit 1
fi

if [[ $# -gt 1 || ( $# -eq 1 && $1 != --build ) ]]; then
  echo "Cách dùng: scripts/start-dev.sh [--build]" >&2
  exit 2
fi

compose=(docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml)
"${compose[@]}" up -d "$@"
"${compose[@]}" ps

published_port="$("${compose[@]}" port frontend 8080)"
echo "Giao diện dev: http://localhost:${published_port##*:}"
echo "Dịch vụ dev đã khởi động. Xem log: cd docker && docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml logs -f"
