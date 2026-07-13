from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trip_planner.app.schemas.cost_coverage import (
    CostCoverageResearchRequest,
    CostCoverageResponse,
    CostCoverageUpdateRequest,
)
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.cost_coverage import (
    CostCoverageUnavailableError,
    get_cost_coverage_payload,
    research_cost_coverage_item,
    update_cost_coverage_item,
)
from trip_planner.app.services.workspace import WorkspaceTripNotFoundError
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["cost-coverage"])


@router.get("/workspace/{trip_id}/cost-coverage", response_model=CostCoverageResponse)
def read_cost_coverage(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> CostCoverageResponse:
    try:
        result = get_cost_coverage_payload(db_session, user=user, trip_id=trip_id)
    except WorkspaceTripNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return CostCoverageResponse.model_validate(result)


@router.patch(
    "/workspace/{trip_id}/cost-coverage/{requirement_code}",
    response_model=CostCoverageResponse,
)
def update_cost_coverage(
    trip_id: str,
    requirement_code: str,
    payload: CostCoverageUpdateRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> CostCoverageResponse:
    try:
        result = update_cost_coverage_item(
            db_session,
            user=user,
            trip_id=trip_id,
            requirement_code=requirement_code,
            updates=payload.model_dump(exclude_none=True),
        )
    except WorkspaceTripNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return CostCoverageResponse.model_validate(result)


@router.post(
    "/workspace/{trip_id}/cost-coverage/{requirement_code}/research",
    response_model=CostCoverageResponse,
)
def research_cost_coverage(
    trip_id: str,
    requirement_code: str,
    payload: CostCoverageResearchRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> CostCoverageResponse:
    try:
        result = research_cost_coverage_item(
            db_session,
            user=user,
            trip_id=trip_id,
            requirement_code=requirement_code,
            inputs=payload.inputs,
        )
    except WorkspaceTripNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CostCoverageUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return CostCoverageResponse.model_validate(result)
