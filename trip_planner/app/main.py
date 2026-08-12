import logging
import math
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from trip_planner.app import APP_VERSION
from trip_planner.app.routes.auth import router as auth_router
from trip_planner.app.routes.budget import router as budget_router
from trip_planner.app.routes.health import router as health_router
from trip_planner.app.routes.inventory import router as inventory_router
from trip_planner.app.routes.planner import router as planner_router
from trip_planner.app.routes.policy import router as policy_router
from trip_planner.app.routes.proposal import router as proposal_router
from trip_planner.app.routes.scenario_history import router as scenario_history_router
from trip_planner.app.routes.trips import router as trips_router
from trip_planner.app.routes.workspace import router as workspace_router
from trip_planner.persistence.db import ensure_database_ready

logger = logging.getLogger(__name__)

_LOCAL_CORS_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173")


def get_allowed_cors_origins() -> list[str]:
    configured_origins = os.getenv("TRIP_PLANNER_CORS_ORIGINS", "")
    origins = list(_LOCAL_CORS_ORIGINS)

    for configured_origin in configured_origins.replace("\n", ",").split(","):
        origin = configured_origin.strip().rstrip("/")
        if origin and origin not in origins:
            origins.append(origin)

    return origins


def get_allowed_cors_origin_regex() -> str | None:
    configured_regex = os.getenv("TRIP_PLANNER_CORS_ORIGIN_REGEX", "").strip()
    return configured_regex or None


def _json_safe_validation_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, Exception):
        return str(value)
    if isinstance(value, list):
        return [_json_safe_validation_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe_validation_value(item) for key, item in value.items()}
    return value


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Resilient startup: a transient or expired database must not crash the whole
    # service. If it did, the health check would fail and every deploy would be
    # marked failed (the exact failure mode when the managed Postgres expired).
    # Degrade instead: keep the API up so /api/health passes, and let DB-backed
    # routes surface their own errors until the database is reachable again.
    try:
        ensure_database_ready()
    except Exception:
        logger.exception(
            "Database initialization failed at startup; continuing in degraded "
            "mode (database-backed routes will error until the database is reachable)."
        )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trip Planner API",
        version=APP_VERSION,
        description="Initial FastAPI runtime for the Trip Planner full-stack application.",
        lifespan=lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_response(
        _: Request, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": _json_safe_validation_value(error.errors())},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_allowed_cors_origins(),
        allow_origin_regex=get_allowed_cors_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(trips_router, prefix="/api")
    app.include_router(inventory_router, prefix="/api")
    app.include_router(planner_router, prefix="/api")
    app.include_router(policy_router, prefix="/api")
    app.include_router(proposal_router, prefix="/api")
    app.include_router(scenario_history_router, prefix="/api")
    app.include_router(workspace_router, prefix="/api")
    app.include_router(budget_router, prefix="/api")

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"message": "Trip Planner API is running."}

    return app


app = create_app()
