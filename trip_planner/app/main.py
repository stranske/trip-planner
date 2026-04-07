from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trip_planner.app.routes.health import router as health_router


app = FastAPI(
    title="Trip Planner API",
    version="0.1.0",
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


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Trip Planner API is running."}

