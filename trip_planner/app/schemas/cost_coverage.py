from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CoverageStatus = Literal[
    "needs_input",
    "research_ready",
    "researched",
    "estimated",
    "evidenced",
    "complete",
    "not_applicable",
]


class CostCoverageUpdateRequest(BaseModel):
    status: CoverageStatus | None = None
    estimate_amount: float | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    note: str | None = None
    source_url: str | None = None
    inputs: dict[str, str] = Field(default_factory=dict)
    selected_option: dict[str, Any] | None = None


class CostCoverageResearchRequest(BaseModel):
    inputs: dict[str, str] = Field(default_factory=dict)


class CostCoverageResponse(BaseModel):
    trip_id: str
    contract_version: str
    source_status: str
    summary: dict[str, Any]
    requirements: list[dict[str, Any]]
    research_notice: dict[str, Any] | None = None
