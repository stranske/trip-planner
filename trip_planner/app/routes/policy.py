from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trip_planner.app.schemas.policy import (
    PolicySyncImportRequest,
    WorkspacePolicyResponse,
)
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.policy import (
    WorkspacePolicyNotFoundError,
    get_workspace_policy_payload,
    import_workspace_policy_constraints,
)
from trip_planner.integrations.tpp import TPPTransportError
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["policy"])


@router.get("/workspace/{trip_id}/policy", response_model=WorkspacePolicyResponse)
def read_workspace_policy(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspacePolicyResponse:
    try:
        payload = get_workspace_policy_payload(db_session, user=user, trip_id=trip_id)
    except WorkspacePolicyNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return WorkspacePolicyResponse.model_validate(payload)


@router.put("/workspace/{trip_id}/policy", response_model=WorkspacePolicyResponse)
def save_workspace_policy(
    trip_id: str,
    payload: PolicySyncImportRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspacePolicyResponse:
    try:
        result = import_workspace_policy_constraints(
            db_session,
            user=user,
            trip_id=trip_id,
            request_payload=payload.request,
            response_payload=payload.response,
            source_kind=payload.source_kind,
            tags=payload.tags,
            notes=payload.notes,
        )
    except WorkspacePolicyNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TPPTransportError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return WorkspacePolicyResponse.model_validate(result)
