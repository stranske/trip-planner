"""Endpoints for the prices a traveller enters by hand."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from trip_planner.app.routes.errors import public_http_error
from trip_planner.app.schemas.trip_prices import (
    TripPricesResponse,
    TripPriceUpsertRequest,
)
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.trip_prices import (
    TripPriceInvalidError,
    TripPriceNotFoundError,
    build_trip_prices_payload,
    read_trip_prices,
    save_trip_price,
)
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["trip-prices"])


@router.get("/workspace/{trip_id}/prices", response_model=TripPricesResponse)
def read_prices(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> TripPricesResponse:
    try:
        rows = read_trip_prices(db_session, user=user, trip_id=trip_id)
    except TripPriceNotFoundError as error:
        raise public_http_error(
            error, status_code=404, message="The requested trip was not found."
        ) from error
    return TripPricesResponse.model_validate(build_trip_prices_payload(rows))


@router.put("/workspace/{trip_id}/prices", response_model=TripPricesResponse)
def save_price(
    trip_id: str,
    payload: TripPriceUpsertRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> TripPricesResponse:
    try:
        rows = save_trip_price(
            db_session,
            user=user,
            trip_id=trip_id,
            component=payload.component,
            amount=payload.amount,
            currency=payload.currency,
            note=payload.note,
            lowest_amount=payload.lowest_amount,
            evidence_attested=payload.evidence_attested,
            cabin_class=payload.cabin_class,
            flight_hours=payload.flight_hours,
        )
    except TripPriceNotFoundError as error:
        raise public_http_error(
            error, status_code=404, message="The requested trip was not found."
        ) from error
    except TripPriceInvalidError as error:
        # The message names the component or the rule that rejected the figure and carries
        # no user data, so it is safe to return verbatim and useful to act on.
        raise public_http_error(error, status_code=422, message=str(error)) from error
    return TripPricesResponse.model_validate(build_trip_prices_payload(rows))
