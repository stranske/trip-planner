#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
preview_url="${TRIP_PLANNER_PREVIEW_URL:-}"
run_local="true"
run_preview="false"

usage() {
  cat <<'EOF'
Usage: scripts/check_production_readiness.sh [--preview <url>] [--preview-only]

Runs the production-focused verification matrix for the planner's critical journeys.

Options:
  --preview <url>   Also run the preview smoke check against the provided deploy URL.
  --preview-only    Skip local checks and run only the preview smoke check.
  --help            Show this help text.

Environment:
  TRIP_PLANNER_PREVIEW_URL   Default preview URL when --preview is omitted.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --preview)
      run_preview="true"
      preview_url="${2:-}"
      if [ -z "${preview_url}" ]; then
        echo "--preview requires a URL argument." >&2
        exit 1
      fi
      shift 2
      ;;
    --preview-only)
      run_local="false"
      run_preview="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [ "${run_preview}" = "true" ] && [ -z "${preview_url}" ]; then
  echo "Preview smoke requested but no preview URL was provided." >&2
  exit 1
fi

cd "${repo_root}"

if [ "${run_local}" = "true" ]; then
  echo "==> Backend critical-journey API checks"
  python -m pytest \
    tests/app/test_auth.py \
    tests/app/test_trip_routes.py \
    tests/app/test_workspace.py \
    tests/app/test_budget_routes.py \
    tests/app/test_policy.py \
    tests/app/test_proposal.py

  echo "==> Frontend critical-route checks"
  npm --prefix frontend run test -- --run \
    src/routes/SignupPage.test.tsx \
    src/routes/LoginPage.test.tsx \
    src/routes/TripsPage.test.tsx \
    src/routes/NewTripPage.test.tsx \
    src/routes/TripDetailPage.test.tsx \
    src/routes/WorkspacePage.test.tsx

  echo "==> Frontend production build"
  npm --prefix frontend run build

  echo "==> Local full-stack smoke check"
  ./scripts/check_full_stack_runtime.sh --smoke-only
fi

if [ "${run_preview}" = "true" ]; then
  preview_url="${preview_url%/}"

  echo "==> Preview smoke check (${preview_url})"
  VITE_API_BASE_URL="${preview_url}" npm --prefix frontend run test:smoke
fi
