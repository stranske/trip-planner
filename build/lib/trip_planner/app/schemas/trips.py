"""Request and response schemas for persisted trip flows."""

from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from trip_planner.contracts.trip import TRAVELER_PARTY_KINDS

TravelerPartyKind = Literal["solo", "pair", "family", "friends", "team"]
DEFAULT_TRAVELER_PARTY_KIND = cast(TravelerPartyKind, TRAVELER_PARTY_KINDS[0])


class _StrictRequest(BaseModel):
    """Refuse fields the API does not know, naming them.

    `POST /api/trips` used to answer 201 for dates and destinations sent beside
    `trip_frame` instead of inside it, silently dropping them, so the trip had no
    destination and no dates (issue 1841).
    """

    model_config = ConfigDict(extra="forbid")


class TravelerPartyRequest(_StrictRequest):
    kind: TravelerPartyKind = Field(default=DEFAULT_TRAVELER_PARTY_KIND)
    traveler_count: int = Field(default=1, ge=1, le=50)
    notes: str = Field(default="", max_length=240)


class TripFrameRequest(_StrictRequest):
    origin: str | None = Field(default=None, max_length=120)
    start_date: str | None = Field(default=None, max_length=32)
    end_date: str | None = Field(default=None, max_length=32)
    duration_days: int | None = Field(default=None, ge=1, le=365)
    primary_regions: list[str] = Field(default_factory=list, max_length=8)
    traveler_party: TravelerPartyRequest = Field(default_factory=TravelerPartyRequest)


class CreateTripRequest(_StrictRequest):
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(default="", max_length=600)
    mode: str = Field(min_length=1, max_length=32)
    trip_frame: TripFrameRequest = Field(default_factory=TripFrameRequest)


class TripFramePatch(_StrictRequest):
    """Only the fields sent are changed; each replaces the stored value."""

    origin: str | None = Field(default=None, max_length=120)
    start_date: str | None = Field(default=None, max_length=32)
    end_date: str | None = Field(default=None, max_length=32)
    duration_days: int | None = Field(default=None, ge=1, le=365)
    primary_regions: list[str] | None = Field(default=None, max_length=8)
    traveler_party: TravelerPartyRequest | None = None


class UpdateTripRequest(_StrictRequest):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    summary: str | None = Field(default=None, max_length=600)
    trip_frame: TripFramePatch | None = None


class TripResponse(BaseModel):
    trip: dict
    #: True when an edit changed what the policy was asked about and the saved verdict
    #: was therefore removed; the client says so rather than letting it vanish silently.
    verdict_cleared: bool = False


class TripListResponse(BaseModel):
    trips: list[dict]


class DeleteTripResponse(BaseModel):
    deleted: bool = True
