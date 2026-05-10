from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trip_planner.app.schemas.workspace import (
    PlanningModeUpdateRequest,
    PlanningLedgerEntry,
    PlanningLedgerEntryCreateRequest,
    PlanningLedgerEntryUpdateRequest,
    PlannerDecisionAnswerRequest,
    PlannerOptionFeedbackRequest,
    RouteOptionActionRequest,
    ScenarioComparisonSurfaceResponse,
    WorkspaceResponse,
)
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.workspace import (
    WorkspaceTripNotFoundError,
    answer_workspace_planner_decision,
    create_planning_ledger_entry,
    get_workspace_scenario_comparison_payload,
    get_workspace_payload,
    submit_workspace_route_option_action,
    submit_workspace_option_feedback,
    update_planning_ledger_entry,
    update_workspace_planning_mode,
)
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["workspace"])


@router.get("/workspace/{trip_id}", response_model=WorkspaceResponse)
def read_workspace(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspaceResponse:
    payload = get_workspace_payload(db_session, user=user, trip_id=trip_id)
    if payload is None:
        raise HTTPException(
            status_code=404, detail=f"Workspace for trip '{trip_id}' was not found."
        )
    return WorkspaceResponse.model_validate(payload)


@router.get(
    "/workspace/{trip_id}/scenarios/compare",
    response_model=ScenarioComparisonSurfaceResponse,
)
def read_workspace_scenario_comparison(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> ScenarioComparisonSurfaceResponse:
    payload = get_workspace_scenario_comparison_payload(
        db_session, user=user, trip_id=trip_id
    )
    if payload is None:
        raise HTTPException(
            status_code=404, detail=f"Workspace for trip '{trip_id}' was not found."
        )
    return ScenarioComparisonSurfaceResponse.model_validate(payload)


@router.put("/workspace/{trip_id}/planning-mode", response_model=WorkspaceResponse)
def update_planning_mode(
    trip_id: str,
    payload: PlanningModeUpdateRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspaceResponse:
    try:
        result = update_workspace_planning_mode(
            db_session,
            user=user,
            trip_id=trip_id,
            planning_mode=payload.planning_mode,
        )
    except WorkspaceTripNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return WorkspaceResponse.model_validate(result)


@router.post(
    "/workspace/{trip_id}/planning-ledger",
    response_model=PlanningLedgerEntry,
)
def create_workspace_planning_ledger_entry(
    trip_id: str,
    payload: PlanningLedgerEntryCreateRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> PlanningLedgerEntry:
    try:
        result = create_planning_ledger_entry(
            db_session,
            user=user,
            trip_id=trip_id,
            item_type=payload.item_type,
            status=payload.status,
            category=payload.category,
            summary=payload.summary,
            detail=payload.detail,
            source_message_ids=payload.source_message_ids,
            source_refs=payload.source_refs,
            related_option_id=payload.related_option_id,
            related_decision_id=payload.related_decision_id,
        )
    except WorkspaceTripNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return PlanningLedgerEntry.model_validate(result)


@router.patch(
    "/workspace/{trip_id}/planning-ledger/{ledger_entry_id}",
    response_model=PlanningLedgerEntry,
)
def patch_workspace_planning_ledger_entry(
    trip_id: str,
    ledger_entry_id: str,
    payload: PlanningLedgerEntryUpdateRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> PlanningLedgerEntry:
    try:
        result = update_planning_ledger_entry(
            db_session,
            user=user,
            trip_id=trip_id,
            ledger_entry_id=ledger_entry_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except WorkspaceTripNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return PlanningLedgerEntry.model_validate(result)


@router.post(
    "/workspace/{trip_id}/planner/decisions/{decision_id}/answer",
    response_model=WorkspaceResponse,
)
def answer_planner_decision(
    trip_id: str,
    decision_id: str,
    payload: PlannerDecisionAnswerRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspaceResponse:
    try:
        result = answer_workspace_planner_decision(
            db_session,
            user=user,
            trip_id=trip_id,
            decision_id=decision_id,
            choice=payload.choice,
        )
    except WorkspaceTripNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return WorkspaceResponse.model_validate(result)


@router.post(
    "/workspace/{trip_id}/planner/options/{option_id}/feedback",
    response_model=WorkspaceResponse,
)
def record_planner_option_feedback(
    trip_id: str,
    option_id: str,
    payload: PlannerOptionFeedbackRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspaceResponse:
    try:
        result = submit_workspace_option_feedback(
            db_session,
            user=user,
            trip_id=trip_id,
            option_id=option_id,
            action_type=payload.action_type,
            decision_id=payload.decision_id,
        )
    except WorkspaceTripNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return WorkspaceResponse.model_validate(result)


@router.post(
    "/workspace/{trip_id}/route-options/{option_id}/action",
    response_model=WorkspaceResponse,
)
def record_route_option_action(
    trip_id: str,
    option_id: str,
    payload: RouteOptionActionRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspaceResponse:
    try:
        result = submit_workspace_route_option_action(
            db_session,
            user=user,
            trip_id=trip_id,
            option_id=option_id,
            action_type=payload.action_type,
        )
    except WorkspaceTripNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return WorkspaceResponse.model_validate(result)
