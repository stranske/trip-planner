from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trip_planner.app.schemas.budget import (
    ActualSpendEventUpsertRequest,
    BudgetPlanUpsertRequest,
    BudgetWorkspaceResponse,
)
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.budget import (
    WorkspaceBudgetNotFoundError,
    get_workspace_budget_payload,
    record_workspace_spend_event,
    update_workspace_spend_event,
    upsert_workspace_budget_plan,
)
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["budget"])


@router.get("/workspace/{trip_id}/budget", response_model=BudgetWorkspaceResponse)
def read_workspace_budget(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> BudgetWorkspaceResponse:
    try:
        payload = get_workspace_budget_payload(db_session, user=user, trip_id=trip_id)
    except WorkspaceBudgetNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return BudgetWorkspaceResponse.model_validate(payload)


@router.put("/workspace/{trip_id}/budget", response_model=BudgetWorkspaceResponse)
def save_workspace_budget(
    trip_id: str,
    payload: BudgetPlanUpsertRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> BudgetWorkspaceResponse:
    try:
        result = upsert_workspace_budget_plan(
            db_session,
            user=user,
            trip_id=trip_id,
            title=payload.title,
            currency=payload.currency,
            current_scenario_budget_id=payload.current_scenario_budget_id,
            tags=payload.tags,
            notes=payload.notes,
            scenario_budgets=[item.model_dump() for item in payload.scenario_budgets],
            summary=payload.summary,
        )
    except WorkspaceBudgetNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return BudgetWorkspaceResponse.model_validate(result)


@router.post("/workspace/{trip_id}/budget/spend-events", response_model=BudgetWorkspaceResponse)
def create_workspace_spend_event(
    trip_id: str,
    payload: ActualSpendEventUpsertRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> BudgetWorkspaceResponse:
    try:
        result = record_workspace_spend_event(
            db_session,
            user=user,
            trip_id=trip_id,
            category_key=payload.category_key,
            amount=payload.amount,
            currency=payload.currency,
            occurred_at=payload.occurred_at,
            source_kind=payload.source_kind,
            source_context=payload.source_context,
            scenario_budget_id=payload.scenario_budget_id,
            saved_scenario_id=payload.saved_scenario_id,
            merchant_name=payload.merchant_name,
            source_ref=payload.source_ref,
            notes=payload.notes,
        )
    except WorkspaceBudgetNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return BudgetWorkspaceResponse.model_validate(result)


@router.patch(
    "/workspace/{trip_id}/budget/spend-events/{spend_event_id}",
    response_model=BudgetWorkspaceResponse,
)
def patch_workspace_spend_event(
    trip_id: str,
    spend_event_id: str,
    payload: ActualSpendEventUpsertRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> BudgetWorkspaceResponse:
    try:
        result = update_workspace_spend_event(
            db_session,
            user=user,
            trip_id=trip_id,
            spend_event_id=spend_event_id,
            category_key=payload.category_key,
            amount=payload.amount,
            currency=payload.currency,
            occurred_at=payload.occurred_at,
            source_kind=payload.source_kind,
            source_context=payload.source_context,
            scenario_budget_id=payload.scenario_budget_id,
            saved_scenario_id=payload.saved_scenario_id,
            merchant_name=payload.merchant_name,
            source_ref=payload.source_ref,
            notes=payload.notes,
        )
    except WorkspaceBudgetNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return BudgetWorkspaceResponse.model_validate(result)
