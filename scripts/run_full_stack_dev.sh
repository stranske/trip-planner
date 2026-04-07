#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_host="${BACKEND_HOST:-127.0.0.1}"
backend_port="${BACKEND_PORT:-8000}"
frontend_host="${FRONTEND_HOST:-127.0.0.1}"
frontend_port="${FRONTEND_PORT:-5173}"

backend_pid=""

cleanup() {
  if [ -n "${backend_pid}" ] && kill -0 "${backend_pid}" 2>/dev/null; then
    kill "${backend_pid}" 2>/dev/null || true
    wait "${backend_pid}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

cd "${repo_root}"

python -m uvicorn trip_planner.app.main:app \
  --reload \
  --host "${backend_host}" \
  --port "${backend_port}" &
backend_pid=$!

cat <<EOF
Trip Planner runtime is starting.
- Backend: http://${backend_host}:${backend_port}
- Frontend: http://${frontend_host}:${frontend_port}

Press Ctrl+C to stop both processes.
EOF

exec npm --prefix "${repo_root}/frontend" run dev -- \
  --host "${frontend_host}" \
  --port "${frontend_port}" \
  --strictPort
