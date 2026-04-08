"""Request and response schemas for persisted trip flows."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TravelerPartyRequest(BaseModel):
    kind: str = Field(default="solo", min_length=1, max_length=32)
    traveler_count: int = Field(default=1, ge=1, le=50)
    notes: str = Field(default="", max_length=240)


class TripFrameRequest(BaseModel):
    start_date: str | None = Field(default=None, max_length=32)
    end_date: str | None = Field(default=None, max_length=32)
    duration_days: int | None = Field(default=None, ge=1, le=365)
    primary_regions: list[str] = Field(default_factory=list, max_length=8)
    traveler_party: TravelerPartyRequest = Field(default_factory=TravelerPartyRequest)


class CreateTripRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(default="", max_length=600)
    mode: str = Field(min_length=1, max_length=32)
    trip_frame: TripFrameRequest = Field(default_factory=TripFrameRequest)


class TripResponse(BaseModel):
    trip: dict


class TripListResponse(BaseModel):
    trips: list[dict]
