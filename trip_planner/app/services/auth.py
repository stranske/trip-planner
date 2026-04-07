"""Authentication helpers for account and session-backed app access."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.persistence.db import get_db_session
from trip_planner.persistence.models.account import UserAccount
from trip_planner.persistence.models.session import AuthSession

SESSION_COOKIE_NAME = "trip_planner_session"
SESSION_TTL_DAYS = 14
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(slots=True)
class AuthenticatedUser:
    user_id: str
    email: str
    display_name: str


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized):
        raise _bad_request("Enter a valid email address.")
    return normalized


def validate_display_name(display_name: str) -> str:
    normalized = display_name.strip()
    if not normalized:
        raise _bad_request("Display name is required.")
    return normalized


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise _bad_request("Password must be at least 8 characters.")
    return password


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return base64.b64encode(salt + digest).decode("ascii")


def verify_password(password: str, encoded_hash: str) -> bool:
    decoded = base64.b64decode(encoded_hash.encode("ascii"))
    salt = decoded[:16]
    stored_digest = decoded[16:]
    provided_digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(stored_digest, provided_digest)


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _serialize_user(user: UserAccount) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
    )


def create_account(
    db_session: Session,
    *,
    email: str,
    password: str,
    display_name: str,
) -> UserAccount:
    normalized_email = normalize_email(email)
    validated_password = validate_password(password)
    validated_name = validate_display_name(display_name)

    existing = db_session.scalar(
        select(UserAccount).where(UserAccount.email == normalized_email)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user = UserAccount(
        user_id=f"user:{secrets.token_hex(8)}",
        email=normalized_email,
        display_name=validated_name,
        password_hash=hash_password(validated_password),
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def authenticate_user(db_session: Session, *, email: str, password: str) -> UserAccount:
    normalized_email = normalize_email(email)
    user = db_session.scalar(select(UserAccount).where(UserAccount.email == normalized_email))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password was not recognized.")
    return user


def create_session_for_user(db_session: Session, *, user: UserAccount) -> tuple[str, AuthSession]:
    raw_token = secrets.token_urlsafe(32)
    session_record = AuthSession(
        session_id=f"session:{secrets.token_hex(8)}",
        user_id=user.user_id,
        token_hash=_hash_session_token(raw_token),
        expires_at=_utcnow() + timedelta(days=SESSION_TTL_DAYS),
    )
    db_session.add(session_record)
    db_session.commit()
    db_session.refresh(session_record)
    return raw_token, session_record


def get_authenticated_user_from_token(
    db_session: Session,
    *,
    token: str | None,
) -> AuthenticatedUser | None:
    if token is None or token.strip() == "":
        return None

    now = _utcnow()
    session_record = db_session.scalar(
        select(AuthSession)
        .where(AuthSession.token_hash == _hash_session_token(token))
        .where(AuthSession.revoked_at.is_(None))
        .where(AuthSession.expires_at > now)
    )
    if session_record is None:
        return None

    session_record.last_seen_at = now
    db_session.commit()
    return _serialize_user(session_record.user)


def revoke_session(db_session: Session, *, token: str | None) -> None:
    if token is None or token.strip() == "":
        return

    session_record = db_session.scalar(
        select(AuthSession).where(AuthSession.token_hash == _hash_session_token(token))
    )
    if session_record is None or session_record.revoked_at is not None:
        return

    session_record.revoked_at = _utcnow()
    db_session.commit()


def require_authenticated_user(
    request: Request,
    db_session: Session = Depends(get_db_session),
) -> AuthenticatedUser:
    user = get_authenticated_user_from_token(
        db_session,
        token=request.cookies.get(SESSION_COOKIE_NAME),
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to access the planner workspace.")
    return user
