from fastapi import APIRouter

from trip_planner.app.schemas.health import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def read_health() -> HealthStatus:
    return HealthStatus(
        service="trip-planner-api",
        status="ok",
        environment="local",
        version="0.1.0",
    )
