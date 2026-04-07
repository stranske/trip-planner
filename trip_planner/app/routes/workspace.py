from fastapi import APIRouter, Depends, HTTPException

from trip_planner.app.schemas.workspace import WorkspaceResponse
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.workspace import get_workspace_payload

router = APIRouter(tags=["workspace"])


@router.get("/workspace/{trip_id}", response_model=WorkspaceResponse)
def read_workspace(
    trip_id: str,
    _: AuthenticatedUser = Depends(require_authenticated_user),
) -> WorkspaceResponse:
    payload = get_workspace_payload(trip_id)
    if payload is None:
        raise HTTPException(
            status_code=404, detail=f"Workspace for trip '{trip_id}' was not found."
        )
    return WorkspaceResponse.model_validate(payload)
