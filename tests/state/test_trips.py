import json
from pathlib import Path

import pytest

from trip_planner.state import (
    PersistedTripArtifactRefs,
    PersistedTripRecord,
    TripStatusChange,
    validate_trip_status_transition,
)
from trip_planner.state.repositories import TripRepository, TripVersion


def _fixture_path(name: str) -> Path:
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "state" / "trips"
    return fixtures_dir / name


def _load_fixture(name: str) -> PersistedTripRecord:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return PersistedTripRecord.from_dict(payload)


def test_trip_record_loads_leisure_draft_fixture() -> None:
    record = _load_fixture("leisure_draft_trip.json")

    payload = record.to_dict()

    assert payload["trip"]["trip_id"] == "trip-leisure-kyoto-draft"
    assert payload["trip"]["status"] == "draft"
    assert payload["artifact_refs"]["scenario_search_id"] == "scenario-search:kyoto-spring"
    assert payload["artifact_refs"]["saved_scenario_ids"] == [
        "saved-scenario:baseline-kyoto",
        "saved-scenario:fallback-osaka",
    ]


def test_trip_record_loads_active_business_fixture() -> None:
    record = _load_fixture("business_active_trip.json")

    assert record.trip.mode == "business"
    assert record.trip.status == "active"
    assert record.artifact_refs.policy_state_id == "policy-state:q2-client-summit"
    assert record.status_history[-1].to_status == "active"


def test_trip_record_loads_archived_fixture() -> None:
    record = _load_fixture("archived_past_trip.json")

    assert record.trip.status == "archived"
    assert record.lifecycle.archived_at == "2025-10-03T18:20:00Z"
    assert record.status_history[-1].to_status == "archived"


def test_validate_trip_status_transition_rejects_skipping_booked_state() -> None:
    with pytest.raises(ValueError, match="active cannot transition to completed"):
        validate_trip_status_transition("active", "completed")


def test_trip_record_rejects_leisure_policy_reference() -> None:
    payload = json.loads(_fixture_path("leisure_draft_trip.json").read_text(encoding="utf-8"))
    payload["artifact_refs"]["policy_state_id"] = "policy-state:should-not-exist"

    with pytest.raises(ValueError, match="leisure trips cannot persist policy_state_id"):
        PersistedTripRecord.from_dict(payload)


def test_trip_record_rejects_duplicate_saved_scenarios() -> None:
    with pytest.raises(ValueError, match="saved_scenario_ids cannot contain duplicates"):
        PersistedTripArtifactRefs(saved_scenario_ids=["saved-scenario:1", "saved-scenario:1"])


def test_trip_record_rejects_string_instead_of_list_for_option_set_ids() -> None:
    with pytest.raises(ValueError, match="option_set_ids must be a list of strings"):
        PersistedTripArtifactRefs(option_set_ids="option-set-1")  # type: ignore[arg-type]


def test_trip_record_rejects_status_history_that_ends_at_wrong_status() -> None:
    payload = json.loads(_fixture_path("business_active_trip.json").read_text(encoding="utf-8"))
    payload["status_history"].append(
        {
            "from_status": "booked",
            "to_status": "archived",
            "changed_at": "2026-04-02T03:00:00Z",
            "reason": "invalid chain for test",
            "actor": "planner",
        }
    )

    with pytest.raises(ValueError, match="status_history must end at the persisted trip status"):
        PersistedTripRecord.from_dict(payload)


def test_trip_repository_protocol_can_store_and_transition_trip_state() -> None:
    class InMemoryTripRepository(TripRepository):
        def __init__(self) -> None:
            self._records: dict[str, PersistedTripRecord] = {}
            self._versions: dict[str, list[TripVersion]] = {}

        def get_trip(self, trip_id: str) -> PersistedTripRecord | None:
            return self._records.get(trip_id)

        def create_trip(
            self,
            trip_record: PersistedTripRecord,
            *,
            summary: str = "",
        ) -> TripVersion:
            self._records[trip_record.trip.trip_id] = trip_record
            version = TripVersion(
                version_id=f"{trip_record.trip.trip_id}-v1",
                trip_id=trip_record.trip.trip_id,
                recorded_at="2026-04-02T04:15:00Z",
                summary=summary,
            )
            self._versions[trip_record.trip.trip_id] = [version]
            return version

        def update_trip(
            self,
            trip_record: PersistedTripRecord,
            *,
            summary: str = "",
        ) -> TripVersion:
            self._records[trip_record.trip.trip_id] = trip_record
            version = TripVersion(
                version_id=(
                    f"{trip_record.trip.trip_id}-v"
                    f"{len(self._versions.get(trip_record.trip.trip_id, [])) + 1}"
                ),
                trip_id=trip_record.trip.trip_id,
                recorded_at="2026-04-02T04:25:00Z",
                summary=summary,
            )
            self._versions.setdefault(trip_record.trip.trip_id, []).append(version)
            return version

        def transition_status(
            self,
            trip_id: str,
            to_status: str,
            *,
            changed_at: str,
            reason: str = "",
            actor: str = "system",
        ) -> TripVersion:
            current = self._records[trip_id]
            from_status = current.trip.status
            validate_trip_status_transition(from_status, to_status)
            current.trip.status = to_status
            current.status_history.append(
                TripStatusChange(
                    from_status=from_status,
                    to_status=to_status,
                    changed_at=changed_at,
                    reason=reason,
                    actor=actor,
                )
            )
            current.lifecycle.updated_at = changed_at
            return self.update_trip(current, summary=reason or f"status -> {to_status}")

        def archive_trip(
            self,
            trip_id: str,
            *,
            archived_at: str,
            reason: str = "",
            actor: str = "system",
        ) -> TripVersion:
            current = self._records[trip_id]
            if current.trip.status != "archived":
                self.transition_status(
                    trip_id,
                    "archived",
                    changed_at=archived_at,
                    reason=reason,
                    actor=actor,
                )
            current.lifecycle.archived_at = archived_at
            return self.update_trip(current, summary=reason or "archived trip")

        def list_trips(
            self,
            *,
            user_id: str | None = None,
            owner_profile_id: str | None = None,
            mode: str | None = None,
            status: str | None = None,
        ) -> list[PersistedTripRecord]:
            results = list(self._records.values())
            if user_id is not None:
                results = [record for record in results if record.trip.user_id == user_id]
            if owner_profile_id is not None:
                results = [
                    record for record in results if record.owner_profile_id == owner_profile_id
                ]
            if mode is not None:
                results = [record for record in results if record.trip.mode == mode]
            if status is not None:
                results = [record for record in results if record.trip.status == status]
            return results

        def list_versions(self, trip_id: str) -> list[TripVersion]:
            return list(self._versions.get(trip_id, []))

    repo = InMemoryTripRepository()
    record = _load_fixture("leisure_draft_trip.json")

    first = repo.create_trip(record, summary="initial import")
    second = repo.transition_status(
        record.trip.trip_id,
        "active",
        changed_at="2026-04-02T04:30:00Z",
        reason="user started planning session",
    )
    archived = repo.archive_trip(
        record.trip.trip_id,
        archived_at="2026-04-02T04:40:00Z",
        reason="trip canceled",
    )

    stored = repo.get_trip(record.trip.trip_id)

    assert stored is not None
    assert stored.trip.status == "archived"
    assert stored.lifecycle.archived_at == "2026-04-02T04:40:00Z"
    assert [version.version_id for version in repo.list_versions(record.trip.trip_id)] == [
        first.version_id,
        second.version_id,
        f"{record.trip.trip_id}-v3",
        archived.version_id,
    ]
    assert repo.list_trips(status="archived")[0].trip.trip_id == record.trip.trip_id


def test_validate_trip_status_transition_rejects_status_without_transition_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(
        __import__("trip_planner.state.trips", fromlist=["ALLOWED_TRIP_STATUS_TRANSITIONS"])
        .ALLOWED_TRIP_STATUS_TRANSITIONS,
        "draft",
        raising=False,
    )

    with pytest.raises(ValueError, match="has no configured transitions"):
        validate_trip_status_transition("draft", "active")


def test_trip_repository_transition_status_allows_empty_history() -> None:
    class InMemoryTripRepository(TripRepository):
        def __init__(self) -> None:
            self._records: dict[str, PersistedTripRecord] = {}
            self._versions: dict[str, list[TripVersion]] = {}

        def get_trip(self, trip_id: str) -> PersistedTripRecord | None:
            return self._records.get(trip_id)

        def create_trip(
            self,
            trip_record: PersistedTripRecord,
            *,
            summary: str = "",
        ) -> TripVersion:
            self._records[trip_record.trip.trip_id] = trip_record
            version = TripVersion(
                version_id=f"{trip_record.trip.trip_id}-v1",
                trip_id=trip_record.trip.trip_id,
                recorded_at="2026-04-02T04:15:00Z",
                summary=summary,
            )
            self._versions[trip_record.trip.trip_id] = [version]
            return version

        def update_trip(
            self,
            trip_record: PersistedTripRecord,
            *,
            summary: str = "",
        ) -> TripVersion:
            self._records[trip_record.trip.trip_id] = trip_record
            version = TripVersion(
                version_id=(
                    f"{trip_record.trip.trip_id}-v"
                    f"{len(self._versions.get(trip_record.trip.trip_id, [])) + 1}"
                ),
                trip_id=trip_record.trip.trip_id,
                recorded_at="2026-04-02T04:25:00Z",
                summary=summary,
            )
            self._versions.setdefault(trip_record.trip.trip_id, []).append(version)
            return version

        def transition_status(
            self,
            trip_id: str,
            to_status: str,
            *,
            changed_at: str,
            reason: str = "",
            actor: str = "system",
        ) -> TripVersion:
            current = self._records[trip_id]
            from_status = current.trip.status
            validate_trip_status_transition(from_status, to_status)
            current.trip.status = to_status
            current.status_history.append(
                TripStatusChange(
                    from_status=from_status,
                    to_status=to_status,
                    changed_at=changed_at,
                    reason=reason,
                    actor=actor,
                )
            )
            current.lifecycle.updated_at = changed_at
            return self.update_trip(current, summary=reason or f"status -> {to_status}")

        def archive_trip(
            self,
            trip_id: str,
            *,
            archived_at: str,
            reason: str = "",
            actor: str = "system",
        ) -> TripVersion:
            raise NotImplementedError

        def list_trips(
            self,
            *,
            user_id: str | None = None,
            owner_profile_id: str | None = None,
            mode: str | None = None,
            status: str | None = None,
        ) -> list[PersistedTripRecord]:
            return list(self._records.values())

        def list_versions(self, trip_id: str) -> list[TripVersion]:
            return list(self._versions.get(trip_id, []))

    repo = InMemoryTripRepository()
    record = _load_fixture("leisure_draft_trip.json")
    record.status_history = []

    repo.create_trip(record, summary="initial import")
    repo.transition_status(
        record.trip.trip_id,
        "active",
        changed_at="2026-04-02T04:30:00Z",
        reason="user started planning session",
    )

    stored = repo.get_trip(record.trip.trip_id)

    assert stored is not None
    assert stored.status_history[-1].from_status == "draft"
    assert stored.status_history[-1].to_status == "active"
