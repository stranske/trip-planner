from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trip_planner.app.schemas.proposal import (
    WorkspaceProposalFollowUpRequest,
    WorkspaceProposalEvaluationRequest,
    WorkspaceProposalResponse,
    WorkspaceProposalSubmissionRequest,
)
from trip_planner.app.services.auth import AuthenticatedUser, require_authenticated_user
from trip_planner.app.services.proposal import (
    WorkspaceProposalNotFoundError,
    get_workspace_proposal_payload,
    save_workspace_proposal_follow_up,
    save_workspace_proposal_evaluation,
    save_workspace_proposal_submission,
)
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["proposal"])


@router.get("/workspace/{trip_id}/proposal", response_model=WorkspaceProposalResponse)
def read_workspace_proposal(
    trip_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspaceProposalResponse:
    try:
        payload = get_workspace_proposal_payload(db_session, user=user, trip_id=trip_id)
    except WorkspaceProposalNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return WorkspaceProposalResponse.model_validate(payload)


@router.put("/workspace/{trip_id}/proposal", response_model=WorkspaceProposalResponse)
def save_workspace_proposal(
    trip_id: str,
    payload: WorkspaceProposalSubmissionRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspaceProposalResponse:
    try:
        result = save_workspace_proposal_submission(
            db_session,
            user=user,
            trip_id=trip_id,
            proposal_payload=payload.proposal,
            request_payload=payload.request,
            response_payload=payload.response,
            proposal_version=payload.proposal_version,
            scenario_id=payload.scenario_id,
        )
    except WorkspaceProposalNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return WorkspaceProposalResponse.model_validate(result)


@router.put("/workspace/{trip_id}/proposal/evaluation", response_model=WorkspaceProposalResponse)
def save_workspace_proposal_result(
    trip_id: str,
    payload: WorkspaceProposalEvaluationRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspaceProposalResponse:
    try:
        result = save_workspace_proposal_evaluation(
            db_session,
            user=user,
            trip_id=trip_id,
            request_payload=payload.request,
            response_payload=payload.response,
            proposal_version=payload.proposal_version,
            scenario_id=payload.scenario_id,
        )
    except WorkspaceProposalNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return WorkspaceProposalResponse.model_validate(result)


@router.patch("/workspace/{trip_id}/proposal/follow-up", response_model=WorkspaceProposalResponse)
def save_workspace_proposal_follow_up_state(
    trip_id: str,
    payload: WorkspaceProposalFollowUpRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db_session: Session = Depends(get_db_session),
) -> WorkspaceProposalResponse:
    try:
        result = save_workspace_proposal_follow_up(
            db_session,
            user=user,
            trip_id=trip_id,
            status=payload.status,
            summary=payload.summary,
            title=payload.title,
            notes=payload.notes,
            selected_alternative=payload.selected_alternative,
            requested_exception=payload.requested_exception,
        )
    except WorkspaceProposalNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return WorkspaceProposalResponse.model_validate(result)
