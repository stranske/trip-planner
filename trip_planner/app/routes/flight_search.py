"""Run a flight search for a trip on request (Duffel test mode: no fare is shown)."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trip_planner.app.routes.errors import public_http_error
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.flight_search import search_trip_flights
from trip_planner.app.services.trip_prices import TripPriceNotFoundError, _require_trip
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["flight-search"])


class FlightSearchResponse(BaseModel):
    status: str = Field(
        description=(
            "not_configured | live_not_enabled | missing_trip_details | no_airport_code | "
            "provider_error | no_offers | test_mode"
        )
    )
    summary: str = Field(description="What the search found, and what to do, in plain words.")
    offer_count: int = 0
    origin_code: str = ""
    destination_code: str = ""
    prices_shown: bool = Field(
        default=False,
        description="Whether any fare from this search is shown. Never, in test mode.",
    )
    issues: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/workspace/{trip_id}/flights/search", response_model=FlightSearchResponse)
def search_flights(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> FlightSearchResponse:
    try:
        record = _require_trip(db_session, user=user, trip_id=trip_id)
    except TripPriceNotFoundError as error:
        raise public_http_error(
            error, status_code=404, message="The requested trip was not found."
        ) from error
    # The loaded scalar fields remain available after detaching; release the
    # connection before waiting on the provider. Dependency cleanup is idempotent.
    db_session.close()
    return FlightSearchResponse.model_validate(search_trip_flights(record).to_dict())
