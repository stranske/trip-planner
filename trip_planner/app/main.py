from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trip_planner.app import APP_VERSION
from trip_planner.app.routes.health import router as health_router
from trip_planner.app.routes.workspace import router as workspace_router

app = FastAPI(
    title="Trip Planner API",
    version=APP_VERSION,
    description="Initial FastAPI runtime for the Trip Planner full-stack application.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(workspace_router, prefix="/api")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Trip Planner API is running."}
