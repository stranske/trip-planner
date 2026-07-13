#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_host="${BACKEND_HOST:-127.0.0.1}"
backend_port="${BACKEND_PORT:-8000}"
frontend_host="${FRONTEND_HOST:-127.0.0.1}"
frontend_port="${FRONTEND_PORT:-5173}"
tpp_repo_path="${TPP_REPO_PATH:-${repo_root}/../Travel-Plan-Permission}"
tpp_host="${TPP_HOST:-127.0.0.1}"
tpp_port="${TPP_PORT:-8766}"
tpp_base_url_was_set="${TPP_BASE_URL:+true}"
tpp_base_url="${TPP_BASE_URL:-http://${tpp_host}:${tpp_port}}"
tpp_runtime_dir=""

backend_pid=""
frontend_pid=""
tpp_pid=""

cleanup() {
  if [ -n "${frontend_pid}" ] && kill -0 "${frontend_pid}" 2>/dev/null; then
    kill "${frontend_pid}" 2>/dev/null || true
    wait "${frontend_pid}" 2>/dev/null || true
  fi
  if [ -n "${backend_pid}" ] && kill -0 "${backend_pid}" 2>/dev/null; then
    kill "${backend_pid}" 2>/dev/null || true
    wait "${backend_pid}" 2>/dev/null || true
  fi
  if [ -n "${tpp_pid}" ] && kill -0 "${tpp_pid}" 2>/dev/null; then
    kill "${tpp_pid}" 2>/dev/null || true
    wait "${tpp_pid}" 2>/dev/null || true
  fi
  if [ -n "${tpp_runtime_dir}" ]; then
    rm -rf "${tpp_runtime_dir}"
  fi
}

trap cleanup EXIT INT TERM

cd "${repo_root}"

if ! curl --fail --silent --show-error "${tpp_base_url}/readyz" >/dev/null 2>&1; then
  if [ "${tpp_base_url_was_set}" = "true" ]; then
    echo "Configured Travel-Plan-Permission service is not ready at ${tpp_base_url}." >&2
    exit 1
  fi
  if [ ! -d "${tpp_repo_path}" ]; then
    echo "Travel-Plan-Permission checkout not found at ${tpp_repo_path}." >&2
    echo "Set TPP_REPO_PATH or start a service and set TPP_BASE_URL." >&2
    exit 1
  fi
  if [ -x "${tpp_repo_path}/.venv/bin/python" ]; then
    tpp_python="${tpp_repo_path}/.venv/bin/python"
  else
    echo "Travel-Plan-Permission needs ${tpp_repo_path}/.venv/bin/python for runtime-dev." >&2
    exit 1
  fi
  tpp_runtime_dir="$(mktemp -d "${TMPDIR:-/tmp}/trip-planner-tpp-runtime.XXXXXX")"
  env \
    PYTHONPATH="${tpp_repo_path}/src" \
    TPP_BASE_URL="${tpp_base_url}" \
    TPP_AUTH_MODE="static-token" \
    TPP_ACCESS_TOKEN="${TPP_ACCESS_TOKEN:-trip-planner-local-token-2026}" \
    TPP_OIDC_PROVIDER="${TPP_OIDC_PROVIDER:-google}" \
    TPP_HANDOFF_SIGNING_SECRET="${TPP_HANDOFF_SIGNING_SECRET:-trip-planner-handoff-secret-2026}" \
    TPP_PORTAL_STATE_PATH="${tpp_runtime_dir}/portal-state.sqlite3" \
    TPP_AUDIT_STATE_PATH="${tpp_runtime_dir}/audit-state.sqlite3" \
    "${tpp_python}" -m travel_plan_permission.http_service \
      --host "${tpp_host}" \
      --port "${tpp_port}" \
      >"${tpp_runtime_dir}/service.stdout" \
      2>"${tpp_runtime_dir}/service.stderr" &
  tpp_pid=$!
  for _attempt in $(seq 1 80); do
    if curl --fail --silent "${tpp_base_url}/readyz" >/dev/null 2>&1; then
      break
    fi
    if ! kill -0 "${tpp_pid}" 2>/dev/null; then
      echo "Travel-Plan-Permission exited during startup:" >&2
      tail -40 "${tpp_runtime_dir}/service.stderr" >&2 || true
      exit 1
    fi
    sleep 0.25
  done
  if ! curl --fail --silent "${tpp_base_url}/readyz" >/dev/null 2>&1; then
    echo "Travel-Plan-Permission did not become ready at ${tpp_base_url}." >&2
    tail -40 "${tpp_runtime_dir}/service.stderr" >&2 || true
    exit 1
  fi
fi

export VITE_TPP_PORTAL_URL="${VITE_TPP_PORTAL_URL:-${tpp_base_url}}"
export TPP_BASE_URL="${tpp_base_url}"
export TPP_ACCESS_TOKEN="${TPP_ACCESS_TOKEN:-trip-planner-local-token-2026}"
export TPP_OIDC_PROVIDER="${TPP_OIDC_PROVIDER:-google}"

python -m uvicorn trip_planner.app.main:app \
  --reload \
  --reload-dir "${repo_root}/trip_planner" \
  --host "${backend_host}" \
  --port "${backend_port}" &
backend_pid=$!

cat <<EOF
Trip Planner runtime is starting.
- Backend: http://${backend_host}:${backend_port}
- Frontend: http://${frontend_host}:${frontend_port}
- TPP portal: ${VITE_TPP_PORTAL_URL}/portal

Press Ctrl+C to stop the local runtime.
EOF

npm --prefix "${repo_root}/frontend" run dev -- \
  --host "${frontend_host}" \
  --port "${frontend_port}" \
  --strictPort &
frontend_pid=$!

wait "${frontend_pid}"
