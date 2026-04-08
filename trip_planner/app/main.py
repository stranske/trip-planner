from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trip_planner.app import APP_VERSION
from trip_planner.app.routes.auth import router as auth_router
from trip_planner.app.routes.health import router as health_router
from trip_planner.app.routes.trips import router as trips_router
from trip_planner.app.routes.workspace import router as workspace_router
from trip_planner.persistence.db import ensure_database_ready


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database_ready()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trip Planner API",
        version=APP_VERSION,
        description="Initial FastAPI runtime for the Trip Planner full-stack application.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(trips_router, prefix="/api")
    app.include_router(workspace_router, prefix="/api")

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"message": "Trip Planner API is running."}

    return app


app = create_app()
