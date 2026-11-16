from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trip_planner.app.schemas.trips import (
    CreateTripRequest,
    DeleteTripResponse,
    TripListResponse,
    TripResponse,
    UpdateTripRequest,
)
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.trips import (
    create_trip,
    delete_trip,
    get_trip,
    list_trips,
    update_trip,
)
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["trips"])


@router.get("/trips", response_model=TripListResponse)
def read_trips(
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> TripListResponse:
    return TripListResponse(trips=list_trips(db_session, user=user))


@router.post("/trips", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip_record(
    payload: CreateTripRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> TripResponse:
    trip = create_trip(
        db_session,
        user=user,
        title=payload.title,
        summary=payload.summary,
        mode=payload.mode,
        origin=payload.trip_frame.origin,
        start_date=payload.trip_frame.start_date,
        end_date=payload.trip_frame.end_date,
        duration_days=payload.trip_frame.duration_days,
        primary_regions=payload.trip_frame.primary_regions,
        traveler_kind=payload.trip_frame.traveler_party.kind,
        traveler_count=payload.trip_frame.traveler_party.traveler_count,
        traveler_notes=payload.trip_frame.traveler_party.notes,
    )
    return TripResponse(trip=trip)


@router.get("/trips/{trip_id}", response_model=TripResponse)
def read_trip_detail(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> TripResponse:
    trip = get_trip(db_session, user=user, trip_id=trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' was not found.")
    return TripResponse(trip=trip)


@router.patch("/trips/{trip_id}", response_model=TripResponse)
def update_trip_record(
    trip_id: str,
    payload: UpdateTripRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> TripResponse:
    changes: dict[str, object] = {
        field: getattr(payload, field)
        for field in ("title", "summary")
        if field in payload.model_fields_set
    }
    frame = payload.trip_frame
    if frame is not None:
        for field in ("origin", "start_date", "end_date", "duration_days", "primary_regions"):
            if field in frame.model_fields_set:
                changes[field] = getattr(frame, field)
        party = frame.traveler_party
        if party is not None:
            changes.update(
                traveler_party_kind=party.kind,
                traveler_count=party.traveler_count,
                traveler_notes=party.notes,
            )
    result = update_trip(db_session, user=user, trip_id=trip_id, changes=changes)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' was not found.")
    trip, determinants = result
    return TripResponse(trip=trip, verdict_cleared=bool(determinants))


@router.delete("/trips/{trip_id}", response_model=DeleteTripResponse)
def delete_trip_record(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> DeleteTripResponse:
    deleted = delete_trip(db_session, user=user, trip_id=trip_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' was not found.")
    return DeleteTripResponse()
