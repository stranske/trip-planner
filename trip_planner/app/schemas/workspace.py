from typing import Any

from pydantic import BaseModel, Field


class WorkspaceResponse(BaseModel):
    trip_record: dict[str, Any] = Field(
        description="Persisted trip record payload for the workspace."
    )
    session: dict[str, Any] = Field(
        description="Current planning session payload for the workspace."
    )
    saved_scenarios: list[dict[str, Any]] = Field(
        description="Persisted saved-scenario records associated with the trip."
    )
    scenario_comparison: dict[str, Any] | None = Field(
        default=None,
        description="Latest scenario comparison metadata when available.",
    )
    scenario_search: dict[str, Any] = Field(
        description="ScenarioSearchResult payload whose route_sequence drives the timeline UI.",
    )
    planner_panel_state: dict[str, Any] = Field(
        description="Workspace-scoped planner panel payload for the mounted side-panel UI.",
    )
