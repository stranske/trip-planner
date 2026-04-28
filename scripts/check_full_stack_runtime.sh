#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Use .venv if present (created by `make install`), otherwise fall back to $PATH python.
if [ -x "${repo_root}/.venv/bin/python" ]; then
  PYTHON="${repo_root}/.venv/bin/python"
else
  PYTHON="python"
fi

backend_host="${BACKEND_HOST:-127.0.0.1}"
backend_port="${BACKEND_PORT:-8000}"
backend_url="http://${backend_host}:${backend_port}"
backend_log="$(mktemp -d "${TMPDIR:-/tmp}/trip-planner-runtime.XXXXXX")/backend.log"
smoke_only="false"
backend_pid=""

prereq_failure() {
  cat >&2 <<'EOF'
Full-stack runtime checks require a virtualenv and both dependency installs.
Run once from the repo root:

  make install

Or manually:
  1. python -m venv .venv && source .venv/bin/activate
  2. python -m pip install -e ".[dev]"
  3. npm --prefix frontend install

Then rerun `make runtime-check` (or `make runtime-smoke`).
`make install` creates .venv and installs both backend and frontend deps;
no manual activation is needed before running make runtime-check afterward.
These commands validate the local FastAPI + Vite MVP in this repo; they do not
prove live Google Maps rendering or remote Travel-Plan-Permission transport.
Do not create a repo-root `node_modules/`; local frontend tooling should live
under `frontend/node_modules`.
Missing integration env vars such as `VITE_GOOGLE_MAPS_EMBED_API_KEY` or
`TPP_BASE_URL` are not prerequisites for these local checks.
EOF
  exit 1
}

require_backend_prereqs() {
  if ! "${PYTHON}" -m pytest --version >/dev/null 2>&1; then
    echo "Missing backend test dependencies (pytest is unavailable under ${PYTHON})." >&2
    prereq_failure
  fi
}

require_frontend_prereqs() {
  if ! npm --prefix frontend exec -- vitest --version >/dev/null 2>&1; then
    echo "Missing frontend test dependencies (`vitest` is unavailable under frontend/node_modules)." >&2
    prereq_failure
  fi
  if ! npm --prefix frontend exec -- vite --version >/dev/null 2>&1; then
    echo "Missing frontend build dependencies (`vite` is unavailable under frontend/node_modules)." >&2
    prereq_failure
  fi
}

if [ "${1:-}" = "--smoke-only" ]; then
  smoke_only="true"
fi

cleanup() {
  if [ -n "${backend_pid}" ] && kill -0 "${backend_pid}" 2>/dev/null; then
    kill "${backend_pid}" 2>/dev/null || true
    wait "${backend_pid}" 2>/dev/null || true
  fi
  if [ -n "${backend_log}" ] && [ -f "${backend_log}" ]; then
    rm -f "${backend_log}"
    rmdir "$(dirname "${backend_log}")" 2>/dev/null || true
  fi
}

wait_for_backend() {
  "${PYTHON}" - "${backend_url}" <<'PY'
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

require_backend_prereqs
require_frontend_prereqs

if [ "${smoke_only}" != "true" ]; then
  "${PYTHON}" -m pytest tests/app/test_health.py tests/app/test_workspace.py
  npm --prefix frontend test
  npm --prefix frontend run build
fi

"${PYTHON}" -m uvicorn trip_planner.app.main:app \
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
