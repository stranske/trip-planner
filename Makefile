.PHONY: runtime-backend runtime-frontend runtime-dev runtime-check runtime-smoke runtime-production-check runtime-preview-smoke

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
