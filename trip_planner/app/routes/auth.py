from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from trip_planner.app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    SessionResponse,
    SessionUserResponse,
    SignupRequest,
)
from trip_planner.app.services.auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_DAYS,
    authenticate_user,
    create_account,
    create_session_for_user,
    get_authenticated_user_from_token,
    revoke_session,
)
from trip_planner.persistence.db import get_db_session

router = APIRouter(tags=["auth"])


def _set_session_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme != "http",
        path="/",
    )


@router.post("/auth/signup", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    db_session: Session = Depends(get_db_session),
) -> SessionResponse:
    user = create_account(
        db_session,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    token, _ = create_session_for_user(db_session, user=user)
    _set_session_cookie(request, response, token)
    return SessionResponse(user=SessionUserResponse.model_validate(user))


@router.post("/auth/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db_session: Session = Depends(get_db_session),
) -> SessionResponse:
    user = authenticate_user(db_session, email=payload.email, password=payload.password)
    token, _ = create_session_for_user(db_session, user=user)
    _set_session_cookie(request, response, token)
    return SessionResponse(user=SessionUserResponse.model_validate(user))


@router.get("/auth/session", response_model=SessionResponse)
def read_session(
    request: Request,
    db_session: Session = Depends(get_db_session),
) -> SessionResponse:
    user = get_authenticated_user_from_token(
        db_session,
        token=request.cookies.get(SESSION_COOKIE_NAME),
    )
    if user is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="No active planner session was found.")
    return SessionResponse(user=SessionUserResponse.model_validate(user))


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    response: Response,
    db_session: Session = Depends(get_db_session),
) -> LogoutResponse:
    revoke_session(db_session, token=request.cookies.get(SESSION_COOKIE_NAME))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return LogoutResponse()
