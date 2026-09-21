from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from trip_planner.app.routes.errors import public_http_error
from trip_planner.app.schemas.policy import (
    PolicySyncImportRequest,
    PolicySyncRequest,
    WorkspacePolicyResponse,
)
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.policy import (
    PolicyConfigurationError,
    WorkspacePolicyNotFoundError,
    get_workspace_policy_payload,
    import_workspace_policy_constraints,
    sync_workspace_policy_from_tpp,
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
        raise public_http_error(
            error,
            status_code=404,
            message="The requested workspace policy was not found.",
        ) from error
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
        raise public_http_error(
            error,
            status_code=404,
            message="The requested workspace policy was not found.",
        ) from error
    except TPPTransportError as error:
        raise public_http_error(
            error,
            status_code=error.status_code,
            message="The policy service could not complete the request.",
        ) from error
    except ValueError as error:
        raise public_http_error(
            error,
            status_code=400,
            message="The workspace policy request was invalid.",
        ) from error
    return WorkspacePolicyResponse.model_validate(result)


@router.post("/workspace/{trip_id}/policy/sync", response_model=WorkspacePolicyResponse)
def sync_workspace_policy(
    trip_id: str,
    payload: PolicySyncRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspacePolicyResponse:
    """Fetch this trip's travel policy from TPP and store it on the workspace.

    The traveller supplies only their organization. The request envelope is built
    server-side from the persisted trip, and no verdict is accepted from the caller.
    """

    try:
        result = sync_workspace_policy_from_tpp(
            db_session,
            user=user,
            trip_id=trip_id,
            organization_id=payload.organization_id,
        )
    except WorkspacePolicyNotFoundError as error:
        raise public_http_error(
            error, status_code=404, message="The requested trip was not found."
        ) from error
    except TPPTransportError as error:
        raise public_http_error(
            error,
            status_code=error.status_code,
            message="The policy service could not be reached, so no policy was applied.",
        ) from error
    except PolicyConfigurationError as error:
        # Safe to surface verbatim: names a configuration key, carries no user data.
        raise public_http_error(error, status_code=503, message=str(error)) from error
    except ValueError as error:
        raise public_http_error(
            error, status_code=400, message="This trip cannot sync policy yet."
        ) from error
    return WorkspacePolicyResponse.model_validate(result)
