#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_host="${BACKEND_HOST:-127.0.0.1}"
backend_port="${BACKEND_PORT:-8000}"
backend_url="http://${backend_host}:${backend_port}"
backend_log="$(mktemp -t trip-planner-runtime)"
smoke_only="false"
backend_pid=""

if [ "${1:-}" = "--smoke-only" ]; then
  smoke_only="true"
fi

cleanup() {
  if [ -n "${backend_pid}" ] && kill -0 "${backend_pid}" 2>/dev/null; then
    kill "${backend_pid}" 2>/dev/null || true
    wait "${backend_pid}" 2>/dev/null || true
  fi
}

wait_for_backend() {
  python - "${backend_url}" <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request

url = sys.argv[1] + "/api/health"

for _ in range(60):
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            payload = json.load(response)
        if payload.get("status") == "ok":
            sys.exit(0)
    except (urllib.error.URLError, TimeoutError):
        time.sleep(0.5)

sys.exit(1)
PY
}

trap cleanup EXIT INT TERM

cd "${repo_root}"

if [ "${smoke_only}" != "true" ]; then
  python -m pytest tests/app/test_health.py tests/app/test_workspace.py
  npm --prefix frontend test
  npm --prefix frontend run build
fi

python -m uvicorn trip_planner.app.main:app \
  --host "${backend_host}" \
  --port "${backend_port}" \
  >"${backend_log}" 2>&1 &
backend_pid=$!

if ! wait_for_backend; then
  cat "${backend_log}" >&2
  echo "Backend runtime failed to start for smoke verification." >&2
  exit 1
fi

VITE_API_BASE_URL="${backend_url}" npm --prefix frontend run test:smoke
