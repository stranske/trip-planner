import json
from pathlib import Path

import pytest

from trip_planner.state import SavedScenarioRecord, ScenarioCheckpoint, ScenarioVersion
from trip_planner.state.repositories import (
    ScenarioCheckpointRepository,
    ScenarioRepository,
)
from trip_planner.state.scenarios import (
    ScenarioArtifactRefs,
    ScenarioComparison,
)


def _fixture_path(name: str) -> Path:
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "state" / "scenarios"
    return fixtures_dir / name


def _load_payload(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def test_saved_scenario_record_loads_leisure_pair_fixture() -> None:
    payload = _load_payload("leisure_baseline_vs_fallback.json")
    baseline = SavedScenarioRecord.from_dict(payload["records"][0])
    fallback = SavedScenarioRecord.from_dict(payload["records"][1])
    comparison = ScenarioComparison.from_dict(payload["comparison"])

    assert baseline.current_version_id == "saved-scenario:kyoto-baseline-v2"
    assert baseline.versions[-1].label == "preferred"
    assert baseline.versions[-1].snapshot_refs.budget_state_id == "budget-state:kyoto-spring"
    assert fallback.versions[0].label == "fallback"
    assert comparison.outcome == "preferred"
    assert comparison.focus_areas == [
        "recovery",
        "route_coherence",
        "weather_resilience",
    ]


def test_saved_scenario_record_loads_business_policy_pair_fixture() -> None:
    payload = _load_payload("business_compliant_vs_exception.json")
    compliant = SavedScenarioRecord.from_dict(payload["records"][0])
    exception = SavedScenarioRecord.from_dict(payload["records"][1])

    assert compliant.versions[0].label == "compliant_first"
    assert compliant.versions[0].snapshot_refs.policy_state_id == "policy-state:q2-client-summit"
    assert exception.versions[0].label == "exception_nearest"
    assert exception.versions[0].snapshot_refs.business_profile_id == "business-profile-consulting"


def test_scenario_checkpoint_loads_in_trip_revision_fixture() -> None:
    payload = _load_payload("in_trip_revision_checkpoint.json")
    record = SavedScenarioRecord.from_dict(payload["record"])
    checkpoint = ScenarioCheckpoint.from_dict(payload["checkpoint"])

    assert record.versions[0].label == "in_trip_revision"
    assert record.versions[0].snapshot_refs.session_state_id == "session-state:kyoto-live"
    assert checkpoint.checkpoint_kind == "in_trip_revision"
    assert checkpoint.pending_decision_ids == [
        "decision:move-temple-visit",
        "decision:confirm-indoor-dinner",
    ]


def test_scenario_artifact_refs_reject_duplicate_option_set_ids() -> None:
    with pytest.raises(ValueError, match="option_set_ids cannot contain duplicates"):
        ScenarioArtifactRefs(
            objective_id="objective:1",
            option_set_ids=["option-set:1", "option-set:1"],
        )


def test_scenario_artifact_refs_accept_profile_only_reference() -> None:
    refs = ScenarioArtifactRefs(leisure_profile_id="leisure-profile:kyoto")

    assert refs.leisure_profile_id == "leisure-profile:kyoto"


def test_scenario_models_reject_string_notes() -> None:
    version = ScenarioVersion(
        version_id="saved-scenario:test-v1",
        saved_scenario_id="saved-scenario:test",
        trip_id="trip-1",
        title="Baseline",
        label="baseline",
        created_at="2026-04-02T12:00:00Z",
        snapshot_refs=ScenarioArtifactRefs(objective_id="objective:1"),
    )

    with pytest.raises(ValueError, match="notes must be a list of strings"):
        ScenarioArtifactRefs(objective_id="objective:1", notes="oops")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="notes must be a list of strings"):
        ScenarioVersion(
            version_id=version.version_id,
            saved_scenario_id=version.saved_scenario_id,
            trip_id=version.trip_id,
            title=version.title,
            label=version.label,
            created_at=version.created_at,
            snapshot_refs=version.snapshot_refs,
            notes="oops",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="notes must be a list of strings"):
        ScenarioComparison(
            comparison_id="comparison:test",
            trip_id="trip-1",
            baseline_scenario_id="saved-scenario:test",
            candidate_scenario_id="saved-scenario:alt",
            compared_at="2026-04-02T12:05:00Z",
            outcome="tradeoff",
            summary="Compare baseline to fallback.",
            notes="oops",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="notes must be a list of strings"):
        SavedScenarioRecord(
            saved_scenario_id="saved-scenario:test",
            trip_id="trip-1",
            current_version_id=version.version_id,
            versions=[version],
            notes="oops",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="notes must be a list of strings"):
        ScenarioCheckpoint(
            checkpoint_id="checkpoint:test",
            trip_id="trip-1",
            saved_scenario_id="saved-scenario:test",
            version_id=version.version_id,
            created_at="2026-04-02T12:10:00Z",
            checkpoint_kind="baseline_capture",
            title="Checkpoint",
            notes="oops",  # type: ignore[arg-type]
        )


def test_scenario_version_requires_snapshot_refs_in_payload() -> None:
    payload = _load_payload("leisure_baseline_vs_fallback.json")["records"][0]["versions"][0]
    payload.pop("snapshot_refs")

    with pytest.raises(ValueError, match="snapshot_refs is required"):
        ScenarioVersion.from_dict(payload)


def test_scenario_version_rejects_in_trip_revision_without_session_reference() -> None:
    with pytest.raises(
        ValueError,
        match="in_trip_revision versions require snapshot_refs.session_state_id",
    ):
        ScenarioVersion(
            version_id="saved-scenario:broken-v1",
            saved_scenario_id="saved-scenario:broken",
            trip_id="trip-1",
            title="Broken in-trip revision",
            label="in_trip_revision",
            created_at="2026-04-02T12:00:00Z",
            snapshot_refs=ScenarioArtifactRefs(objective_id="objective:1"),
        )


def test_saved_scenario_record_rejects_unknown_current_version() -> None:
    payload = _load_payload("leisure_baseline_vs_fallback.json")["records"][0]
    payload["current_version_id"] = "saved-scenario:missing"

    with pytest.raises(ValueError, match="current_version_id must reference a saved version"):
        SavedScenarioRecord.from_dict(payload)


def test_scenario_repository_protocol_can_restore_and_compare_versions() -> None:
    class InMemoryScenarioRepository(ScenarioRepository):
        def __init__(self) -> None:
            self._records: dict[str, SavedScenarioRecord] = {}
            self._comparisons: list[ScenarioComparison] = []

        def get_scenario(self, saved_scenario_id: str) -> SavedScenarioRecord | None:
            return self._records.get(saved_scenario_id)

        def save_scenario(
            self,
            scenario: SavedScenarioRecord,
            *,
            summary: str = "",
        ) -> ScenarioVersion:
            self._records[scenario.saved_scenario_id] = scenario
            active = next(
                version
                for version in scenario.versions
                if version.version_id == scenario.current_version_id
            )
            if summary:
                active.summary = summary
            return active

        def restore_scenario(
            self,
            saved_scenario_id: str,
            version_id: str,
            *,
            restored_at: str,
            actor: str = "system",
            summary: str = "",
        ) -> ScenarioVersion:
            record = self._records[saved_scenario_id]
            source = next(
                version for version in record.versions if version.version_id == version_id
            )
            restored = ScenarioVersion(
                version_id=f"{saved_scenario_id}-v{len(record.versions) + 1}",
                saved_scenario_id=saved_scenario_id,
                trip_id=record.trip_id,
                title=f"{source.title} restored",
                label=source.label,
                created_at=restored_at,
                created_by=actor,
                scope=source.scope,
                snapshot_refs=source.snapshot_refs,
                based_on_version_id=source.version_id,
                summary=summary or f"restored {source.version_id}",
                tags=list(source.tags),
                notes=list(source.notes) + [f"Restored from {source.version_id}."],
            )
            record.versions.append(restored)
            record.current_version_id = restored.version_id
            return restored

        def list_scenarios(
            self,
            *,
            trip_id: str | None = None,
            label: str | None = None,
        ) -> list[SavedScenarioRecord]:
            results = list(self._records.values())
            if trip_id is not None:
                results = [record for record in results if record.trip_id == trip_id]
            if label is not None:
                results = [
                    record
                    for record in results
                    if any(
                        version.version_id == record.current_version_id and version.label == label
                        for version in record.versions
                    )
                ]
            return results

        def list_versions(self, saved_scenario_id: str) -> list[ScenarioVersion]:
            return list(self._records[saved_scenario_id].versions)

        def compare_scenarios(
            self,
            baseline_scenario_id: str,
            candidate_scenario_id: str,
            *,
            compared_at: str,
            summary: str,
            outcome: str = "tradeoff",
            focus_areas: list[str] | None = None,
        ) -> ScenarioComparison:
            baseline = self._records[baseline_scenario_id]
            comparison = ScenarioComparison(
                comparison_id=f"comparison:{baseline_scenario_id}:{candidate_scenario_id}",
                trip_id=baseline.trip_id,
                baseline_scenario_id=baseline_scenario_id,
                candidate_scenario_id=candidate_scenario_id,
                compared_at=compared_at,
                outcome=outcome,
                summary=summary,
                focus_areas=list(focus_areas or []),
            )
            self._comparisons.append(comparison)
            return comparison

    payload = _load_payload("leisure_baseline_vs_fallback.json")
    baseline = SavedScenarioRecord.from_dict(payload["records"][0])
    fallback = SavedScenarioRecord.from_dict(payload["records"][1])

    repo = InMemoryScenarioRepository()
    repo.save_scenario(baseline)
    repo.save_scenario(fallback)

    restored = repo.restore_scenario(
        baseline.saved_scenario_id,
        "saved-scenario:kyoto-baseline-v1",
        restored_at="2026-04-02T10:00:00Z",
        actor="planner",
        summary="Restored the original baseline after later edits drifted.",
    )
    comparison = repo.compare_scenarios(
        baseline.saved_scenario_id,
        fallback.saved_scenario_id,
        compared_at="2026-04-02T10:05:00Z",
        summary="Fallback stays available while the restored baseline is active.",
        outcome="preferred",
        focus_areas=["route_coherence", "rollback"],
    )

    current_record = repo.get_scenario(baseline.saved_scenario_id)

    assert restored.based_on_version_id == "saved-scenario:kyoto-baseline-v1"
    assert current_record is not None
    assert current_record.current_version_id == restored.version_id
    assert len(repo.list_versions(baseline.saved_scenario_id)) == 3
    assert repo.list_scenarios(label="fallback")[0].saved_scenario_id == fallback.saved_scenario_id
    assert comparison.outcome == "preferred"
    assert comparison.focus_areas == ["route_coherence", "rollback"]


def test_scenario_checkpoint_repository_protocol_can_filter_checkpoints() -> None:
    class InMemoryCheckpointRepository(ScenarioCheckpointRepository):
        def __init__(self) -> None:
            self._checkpoints: dict[str, ScenarioCheckpoint] = {}

        def get_checkpoint(self, checkpoint_id: str) -> ScenarioCheckpoint | None:
            return self._checkpoints.get(checkpoint_id)

        def create_checkpoint(self, checkpoint: ScenarioCheckpoint) -> ScenarioCheckpoint:
            self._checkpoints[checkpoint.checkpoint_id] = checkpoint
            return checkpoint

        def list_checkpoints(
            self,
            *,
            trip_id: str | None = None,
            saved_scenario_id: str | None = None,
            checkpoint_kind: str | None = None,
        ) -> list[ScenarioCheckpoint]:
            results = list(self._checkpoints.values())
            if trip_id is not None:
                results = [item for item in results if item.trip_id == trip_id]
            if saved_scenario_id is not None:
                results = [item for item in results if item.saved_scenario_id == saved_scenario_id]
            if checkpoint_kind is not None:
                results = [item for item in results if item.checkpoint_kind == checkpoint_kind]
            return results

    payload = _load_payload("in_trip_revision_checkpoint.json")
    checkpoint = ScenarioCheckpoint.from_dict(payload["checkpoint"])

    repo = InMemoryCheckpointRepository()
    repo.create_checkpoint(checkpoint)

    assert repo.get_checkpoint(checkpoint.checkpoint_id) is checkpoint
    assert repo.list_checkpoints(trip_id="trip-leisure-kyoto-live")[0] is checkpoint
    assert repo.list_checkpoints(checkpoint_kind="in_trip_revision")[0] is checkpoint
