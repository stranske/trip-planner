"""Backend-neutral repository interfaces for saved-scenario state."""

from __future__ import annotations

from typing import Protocol

from trip_planner.state.scenarios import (
    SavedScenarioRecord,
    ScenarioCheckpoint,
    ScenarioComparison,
    ScenarioVersion,
)


class ScenarioRepository(Protocol):
    def get_scenario(self, saved_scenario_id: str) -> SavedScenarioRecord | None:
        """Load one persisted saved-scenario record."""

    def save_scenario(
        self,
        scenario: SavedScenarioRecord,
        *,
        summary: str = "",
    ) -> ScenarioVersion:
        """Persist one saved-scenario record and return the active version metadata."""

    def restore_scenario(
        self,
        saved_scenario_id: str,
        version_id: str,
        *,
        restored_at: str,
        actor: str = "system",
        summary: str = "",
    ) -> ScenarioVersion:
        """Restore a prior saved-scenario version and return the new active version."""

    def list_scenarios(
        self,
        *,
        trip_id: str | None = None,
        label: str | None = None,
    ) -> list[SavedScenarioRecord]:
        """List persisted saved scenarios, optionally filtered by trip or active label."""

    def list_versions(self, saved_scenario_id: str) -> list[ScenarioVersion]:
        """List all saved versions for one scenario record."""

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
        """Persist or return comparison metadata for two saved scenarios."""


class ScenarioCheckpointRepository(Protocol):
    def get_checkpoint(self, checkpoint_id: str) -> ScenarioCheckpoint | None:
        """Load one saved checkpoint record."""

    def create_checkpoint(self, checkpoint: ScenarioCheckpoint) -> ScenarioCheckpoint:
        """Persist a new checkpoint tied to a saved scenario version."""

    def list_checkpoints(
        self,
        *,
        trip_id: str | None = None,
        saved_scenario_id: str | None = None,
        checkpoint_kind: str | None = None,
    ) -> list[ScenarioCheckpoint]:
        """List saved checkpoints using backend-neutral filters."""
