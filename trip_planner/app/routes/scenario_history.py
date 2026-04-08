from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from trip_planner.app.schemas.scenario_history import (
    CreatePlanningHistoryRequest,
    CreatePlanningSessionRequest,
    CreateSavedScenarioRequest,
    PlanningHistoryResponse,
    PlanningSessionResponse,
    SavedScenarioResponse,
    TripScenarioHistoryResponse,
)
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.scenario_history import (
    create_planning_history_entry,
    create_planning_session,
    create_saved_scenario,
    list_trip_scenario_history,
)
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["trip-scenarios"])


@router.get("/trips/{trip_id}/scenario-history", response_model=TripScenarioHistoryResponse)
def read_trip_scenario_history(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> TripScenarioHistoryResponse:
    return TripScenarioHistoryResponse.model_validate(
        list_trip_scenario_history(db_session, user=user, trip_id=trip_id)
    )


@router.post(
    "/trips/{trip_id}/saved-scenarios",
    response_model=SavedScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trip_saved_scenario(
    trip_id: str,
    payload: CreateSavedScenarioRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> SavedScenarioResponse:
    return SavedScenarioResponse(
        saved_scenario=create_saved_scenario(
            db_session,
            user=user,
            trip_id=trip_id,
            payload=payload.model_dump(),
        )
    )


@router.post(
    "/trips/{trip_id}/planning-history",
    response_model=PlanningHistoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trip_planning_history(
    trip_id: str,
    payload: CreatePlanningHistoryRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> PlanningHistoryResponse:
    return PlanningHistoryResponse(
        planning_history_entry=create_planning_history_entry(
            db_session,
            user=user,
            trip_id=trip_id,
            payload=payload.model_dump(),
        )
    )


@router.post(
    "/trips/{trip_id}/planning-sessions",
    response_model=PlanningSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trip_planning_session(
    trip_id: str,
    payload: CreatePlanningSessionRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> PlanningSessionResponse:
    return PlanningSessionResponse(
        planning_session=create_planning_session(
            db_session,
            user=user,
            trip_id=trip_id,
            payload=payload.model_dump(),
        )
    )
