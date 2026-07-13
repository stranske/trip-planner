.PHONY: test install runtime-backend runtime-frontend runtime-dev runtime-check runtime-smoke runtime-production-check runtime-preview-smoke runtime-full-product-check full-product-check two-trip-ui-canary two-trip-demo

test:
	python -m pytest

install:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	npm --prefix frontend ci

runtime-backend:
	python -m uvicorn trip_planner.app.main:app --reload --host 127.0.0.1 --port 8000

runtime-frontend:
	npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort

runtime-dev:
	./scripts/run_full_stack_dev.sh

runtime-check:
	./scripts/check_full_stack_runtime.sh

runtime-smoke:
	./scripts/check_full_stack_runtime.sh --smoke-only

runtime-production-check:
	./scripts/check_production_readiness.sh

runtime-preview-smoke:
	./scripts/check_production_readiness.sh --preview "${TRIP_PLANNER_PREVIEW_URL}"

# LIVE_TPP: pass --live-tpp <mode> (auto|off|required).  Set LIVE_TPP=required
# in CI (with TPP_REPO_PATH) to gate on the live cross-repo handshake.
LIVE_TPP ?= auto

full-product-check:
	@echo "Live TPP auto-start resolves Python as TPP .venv/bin/python, then uv run from uv.lock, then fails fast; set TPP_BASE_URL to skip auto-start."
	python scripts/check_full_product_verification.py --live-tpp $(LIVE_TPP)

runtime-full-product-check: full-product-check

two-trip-ui-canary:
	./scripts/run_two_trip_ui_canary.sh

two-trip-demo:
	TRIP_PLANNER_SEED_DEMO=1 uv run --extra dev python scripts/seed_demo_data.py
