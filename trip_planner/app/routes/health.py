import os

from fastapi import APIRouter, Request

from trip_planner.app.schemas.health import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def read_health(request: Request) -> HealthStatus:
    return HealthStatus(
        service="trip-planner-api",
        status="ok",
        environment=os.getenv("TRIP_PLANNER_ENV", "local"),
        version=request.app.version,
    )
