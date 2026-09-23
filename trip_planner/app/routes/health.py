import os

from fastapi import APIRouter, Request

from trip_planner.app.database_status import DatabaseStatus
from trip_planner.app.schemas.health import DatabaseHealth, HealthStatus
from trip_planner.persistence import db

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def read_health(request: Request) -> HealthStatus:
    # Always 200, so a deploy is not failed by the database; the body says whether it is usable.
    status = getattr(request.app.state, "database_status", None)
    if not isinstance(status, DatabaseStatus):
        # Startup did not run (an app served without its lifespan): check now rather than assume.
        status = DatabaseStatus(initialise=lambda: db.ensure_database_ready())
        request.app.state.database_status = status
    status.refresh_if_due()
    return HealthStatus(
        service="trip-planner-api",
        status="ok" if status.ready else "degraded",
        environment=os.getenv("TRIP_PLANNER_ENV", "local"),
        version=request.app.version,
        database=DatabaseHealth(
            ready=status.ready,
            reason=status.reason,
            checked_at=status.checked_at.isoformat() if status.checked_at else None,
        ),
    )
