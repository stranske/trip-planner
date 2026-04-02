"""Backend-neutral repository interfaces for persisted account state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from trip_planner.contracts._validators import require_non_empty
from trip_planner.state.accounts import TravelerProfile, User


@dataclass(slots=True)
class AccountVersion:
    version_id: str
    user_id: str
    recorded_at: str
    summary: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.version_id, "version_id")
        require_non_empty(self.user_id, "user_id")
        require_non_empty(self.recorded_at, "recorded_at")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AccountRepository(Protocol):
    def get_user(self, user_id: str) -> User | None:
        """Load one persisted user account."""

    def save_user(self, user: User, *, summary: str = "") -> AccountVersion:
        """Persist a user account snapshot and return its version metadata."""

    def list_users(self) -> list[User]:
        """List the currently persisted user accounts."""

    def list_versions(self, user_id: str) -> list[AccountVersion]:
        """List saved versions for one user account."""


class TravelerProfileRepository(Protocol):
    def list_profiles(self, user_id: str) -> list[TravelerProfile]:
        """List the persisted traveler profiles owned by one user."""

    def save_profile(
        self,
        user_id: str,
        profile: TravelerProfile,
        *,
        summary: str = "",
    ) -> AccountVersion:
        """Persist a traveler profile update and return version metadata."""
