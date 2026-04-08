"""Services for persisted trip create/list/detail flows."""

from __future__ import annotations

import re
import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.contracts.trip import (
    ProfileRefs,
    TravelerPartySummary,
    Trip,
    TripArtifactRefs,
    TripFrameSummary,
)
from trip_planner.persistence.models.trip import PersistedTrip

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_TRIP_ID_PREFIX = "trip-"
_TRIP_ID_RANDOM_HEX_LENGTH = 6
_MAX_TRIP_ID_LENGTH = 96
_MAX_TRIP_ID_SLUG_LENGTH = (
    _MAX_TRIP_ID_LENGTH - len(_TRIP_ID_PREFIX) - 1 - _TRIP_ID_RANDOM_HEX_LENGTH
)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def _slugify_title(title: str) -> str:
    slug = _SLUG_RE.sub("-", title.strip().lower()).strip("-")
    slug = slug[:_MAX_TRIP_ID_SLUG_LENGTH].strip("-")
    return slug or "trip"


def _generate_trip_id(title: str) -> str:
    return f"{_TRIP_ID_PREFIX}{_slugify_title(title)}-{secrets.token_hex(3)}"


def _default_profile_refs(mode: str, trip_id: str) -> ProfileRefs:
    if mode == "leisure":
        return ProfileRefs(leisure_profile_id=f"profile:{trip_id}:leisure")
    if mode == "business":
        return ProfileRefs(business_profile_id=f"profile:{trip_id}:business")
    raise _bad_request("Trip mode must be either 'leisure' or 'business'.")


def _normalize_regions(primary_regions: list[str]) -> list[str]:
    normalized = [region.strip() for region in primary_regions if region.strip()]
    deduped: list[str] = []
    for region in normalized:
        if region not in deduped:
            deduped.append(region)
    return deduped


def _build_trip_record(
    *,
    user: AuthenticatedUser,
    title: str,
    summary: str,
    mode: str,
    start_date: str | None,
    end_date: str | None,
    duration_days: int | None,
    primary_regions: list[str],
    traveler_kind: str,
    traveler_count: int,
    traveler_notes: str,
) -> PersistedTrip:
    trip_id = _generate_trip_id(title)
    profile_refs = _default_profile_refs(mode, trip_id)

    return PersistedTrip(
        trip_id=trip_id,
        user_id=user.user_id,
        title=title.strip(),
        summary=summary.strip(),
        mode=mode,
        status="draft",
        start_date=start_date,
        end_date=end_date,
        duration_days=duration_days,
        primary_regions=primary_regions,
        traveler_party_kind=traveler_kind,
        traveler_count=traveler_count,
        traveler_notes=traveler_notes.strip(),
        leisure_profile_id=profile_refs.leisure_profile_id,
        business_profile_id=profile_refs.business_profile_id,
        option_set_ids=[],
    )


def serialize_trip(record: PersistedTrip) -> dict:
    contract = Trip(
        trip_id=record.trip_id,
        user_id=record.user_id,
        mode=record.mode,
        status=record.status,
        title=record.title,
        summary=record.summary,
        trip_frame=TripFrameSummary(
            start_date=record.start_date,
            end_date=record.end_date,
            duration_days=record.duration_days,
            primary_regions=list(record.primary_regions),
            traveler_party=TravelerPartySummary(
                kind=record.traveler_party_kind,
                traveler_count=record.traveler_count,
                notes=record.traveler_notes,
            ),
        ),
        profile_refs=ProfileRefs.from_dict(record.profile_refs_payload()),
        artifacts=TripArtifactRefs.from_dict(record.artifacts_payload()),
    )
    return contract.to_dict()


def create_trip(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    title: str,
    summary: str,
    mode: str,
    start_date: str | None,
    end_date: str | None,
    duration_days: int | None,
    primary_regions: list[str],
    traveler_kind: str,
    traveler_count: int,
    traveler_notes: str,
) -> dict:
    normalized_title = title.strip()
    if not normalized_title:
        raise _bad_request("Trip title is required.")

    record = _build_trip_record(
        user=user,
        title=normalized_title,
        summary=summary,
        mode=mode,
        start_date=start_date.strip() if start_date else None,
        end_date=end_date.strip() if end_date else None,
        duration_days=duration_days,
        primary_regions=_normalize_regions(primary_regions),
        traveler_kind=traveler_kind,
        traveler_count=traveler_count,
        traveler_notes=traveler_notes,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return serialize_trip(record)


def list_trips(db_session: Session, *, user: AuthenticatedUser) -> list[dict]:
    records = db_session.scalars(
        select(PersistedTrip)
        .where(PersistedTrip.user_id == user.user_id)
        .order_by(PersistedTrip.updated_at.desc(), PersistedTrip.trip_id.asc())
    ).all()
    return [serialize_trip(record) for record in records]


def get_trip(db_session: Session, *, user: AuthenticatedUser, trip_id: str) -> dict | None:
    record = db_session.scalar(
        select(PersistedTrip)
        .where(PersistedTrip.trip_id == trip_id)
        .where(PersistedTrip.user_id == user.user_id)
    )
    if record is None:
        return None
    return serialize_trip(record)
