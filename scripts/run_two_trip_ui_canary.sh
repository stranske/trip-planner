#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_port="${TRIP_PLANNER_CANARY_BACKEND_PORT:-8000}"
frontend_port="${TRIP_PLANNER_CANARY_FRONTEND_PORT:-5173}"
backend_url="http://127.0.0.1:${backend_port}"
frontend_url="http://127.0.0.1:${frontend_port}"
run_dir="$(mktemp -d "${TMPDIR:-/tmp}/trip-planner-two-trip-canary.XXXXXX")"
artifact_dir="${TRIP_PLANNER_CANARY_ARTIFACT_DIR:-${run_dir}/artifacts}"
backend_log="${run_dir}/backend.log"
frontend_log="${run_dir}/frontend.log"
backend_pid=""
frontend_pid=""

cleanup() {
  if [ -n "${frontend_pid}" ] && kill -0 "${frontend_pid}" 2>/dev/null; then
    kill "${frontend_pid}" 2>/dev/null || true
    wait "${frontend_pid}" 2>/dev/null || true
  fi
  if [ -n "${backend_pid}" ] && kill -0 "${backend_pid}" 2>/dev/null; then
    kill "${backend_pid}" 2>/dev/null || true
    wait "${backend_pid}" 2>/dev/null || true
  fi
}

show_failure_logs() {
  echo "Two-trip UI canary failed. Backend log tail:"
  tail -80 "${backend_log}" 2>/dev/null || true
  echo "Frontend log tail:"
  tail -80 "${frontend_log}" 2>/dev/null || true
}

wait_for_url() {
  local url="$1"
  local attempts=60
  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl --fail --silent --show-error "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

trap cleanup EXIT INT TERM
trap show_failure_logs ERR

mkdir -p "${artifact_dir}"
cd "${repo_root}"

TRIP_PLANNER_DATABASE_URL="sqlite:///${run_dir}/canary.sqlite3" \
TRIP_PLANNER_CORS_ORIGINS="${frontend_url}" \
  uv run --extra dev python -m uvicorn trip_planner.app.main:app \
  --host 127.0.0.1 --port "${backend_port}" >"${backend_log}" 2>&1 &
backend_pid=$!
wait_for_url "${backend_url}/api/health"

VITE_API_BASE_URL="${backend_url}" frontend/node_modules/.bin/vite frontend \
  --host 127.0.0.1 --port "${frontend_port}" --strictPort >"${frontend_log}" 2>&1 &
frontend_pid=$!
wait_for_url "${frontend_url}/signup"

TRIP_PLANNER_CANARY_BASE_URL="${frontend_url}" \
TRIP_PLANNER_CANARY_ARTIFACT_DIR="${artifact_dir}" \
  npm --prefix frontend run test:e2e:canary

echo "Two-trip UI canary PASS. Browser artifacts: ${artifact_dir}"
