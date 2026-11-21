from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trip_planner.app.routes.errors import public_http_error
from trip_planner.app.schemas.planner import PlannerSessionResponse, PlannerTurnRequest
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.planner import (
    WorkspacePlannerTripNotFoundError,
    get_planner_session_payload,
    resume_planner_session_payload,
    submit_in_trip_event,
    submit_planner_turn,
)
from trip_planner.app.services.planner_in_trip import InTripEventConflictError
from trip_planner.app.services.workspace import WorkspaceTripNotFoundError
from trip_planner.orchestration import InTripTriggerEvent
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["planner"])


@router.get("/planner/{trip_id}/session", response_model=PlannerSessionResponse)
def read_planner_session(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> PlannerSessionResponse:
    try:
        payload = get_planner_session_payload(db_session, user=user, trip_id=trip_id)
    except WorkspacePlannerTripNotFoundError as error:
        raise public_http_error(
            error, status_code=404, message="The requested planner session was not found."
        ) from error
    return PlannerSessionResponse.model_validate(payload)


@router.post("/planner/{trip_id}/resume", response_model=PlannerSessionResponse)
def resume_planner_session(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> PlannerSessionResponse:
    try:
        payload = resume_planner_session_payload(db_session, user=user, trip_id=trip_id)
    except WorkspacePlannerTripNotFoundError as error:
        raise public_http_error(
            error, status_code=404, message="The requested planner session was not found."
        ) from error
    return PlannerSessionResponse.model_validate(payload)


@router.post("/planner/{trip_id}/turns", response_model=PlannerSessionResponse)
def create_planner_turn(
    trip_id: str,
    payload: PlannerTurnRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> PlannerSessionResponse:
    try:
        result = submit_planner_turn(
            db_session,
            user=user,
            trip_id=trip_id,
            message=payload.message,
            tool_calls=[item.model_dump() for item in payload.tool_calls],
        )
    except WorkspacePlannerTripNotFoundError as error:
        raise public_http_error(
            error, status_code=404, message="The requested planner session was not found."
        ) from error
    except ValueError as error:
        raise public_http_error(
            error, status_code=400, message="The planner request was invalid."
        ) from error
    return PlannerSessionResponse.model_validate(result)


@router.post("/planner/{trip_id}/in-trip-events", response_model=PlannerSessionResponse)
def process_in_trip_event(
    trip_id: str,
    event: InTripTriggerEvent,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> PlannerSessionResponse:
    try:
        result = submit_in_trip_event(db_session, user=user, trip_id=trip_id, event=event)
    except WorkspaceTripNotFoundError as error:
        raise public_http_error(
            error,
            status_code=404,
            message="The requested planner session was not found.",
        ) from error
    except InTripEventConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise public_http_error(
            error, status_code=400, message="The in-trip event could not be applied."
        ) from error
    return PlannerSessionResponse.model_validate(result)
