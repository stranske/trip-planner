from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

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


def _request_is_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", maxsplit=1)[0]
    return request.url.scheme == "https" or forwarded_proto.strip().lower() == "https"


def _is_cross_site_request(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return False

    origin_host = urlsplit(origin).hostname
    request_host = request.url.hostname
    if origin_host is None or request_host is None:
        return False

    return origin_host.lower() != request_host.lower()


def _set_session_cookie(request: Request, response: Response, token: str) -> None:
    is_https = _request_is_https(request)
    samesite: Literal["none", "lax"] = "none" if is_https and _is_cross_site_request(request) else "lax"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite=samesite,
        secure=is_https,
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
