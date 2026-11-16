"""Backend-neutral repository interfaces for persisted trip state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from trip_planner.contracts._validators import require_non_empty
from trip_planner.state.trips import PersistedTripRecord


@dataclass(slots=True)
class TripVersion:
    version_id: str
    trip_id: str
    recorded_at: str
    summary: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.version_id, "version_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.recorded_at, "recorded_at")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TripRepository(Protocol):
    def get_trip(self, trip_id: str) -> PersistedTripRecord | None:
        """Load one persisted trip record."""

    def create_trip(
        self,
        trip_record: PersistedTripRecord,
        *,
        summary: str = "",
    ) -> TripVersion:
        """Persist a new trip record and return its version metadata."""

    def update_trip(
        self,
        trip_record: PersistedTripRecord,
        *,
        summary: str = "",
    ) -> TripVersion:
        """Persist an updated trip record and return its version metadata."""

    def transition_status(
        self,
        trip_id: str,
        to_status: str,
        *,
        changed_at: str,
        reason: str = "",
        actor: str = "system",
    ) -> TripVersion:
        """Persist a status transition for one trip."""

    def archive_trip(
        self,
        trip_id: str,
        *,
        archived_at: str,
        reason: str = "",
        actor: str = "system",
    ) -> TripVersion:
        """Archive one trip and return its version metadata."""

    def list_trips(
        self,
        *,
        user_id: str | None = None,
        owner_profile_id: str | None = None,
        mode: str | None = None,
        status: str | None = None,
    ) -> list[PersistedTripRecord]:
        """List trip records using backend-neutral filters."""

    def list_versions(self, trip_id: str) -> list[TripVersion]:
        """List saved versions for one persisted trip."""
