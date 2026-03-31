"""Reusable provenance references for source-backed planning objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_optional_non_empty,
    require_strings,
)

from . import schema
from .models import QualityValueFitSummary, SourceTrustSignals


@dataclass(slots=True)
class ProvenanceReference:
    provenance_id: str
    source_id: str
    source_category: str
    subject_kind: str
    subject_id: str
    contribution_kind: str
    summary: str
    locator: str = ""
    captured_at: str = ""
    freshness_days_at_capture: int | None = None
    trust_snapshot: SourceTrustSignals | None = None
    quality_value_fit: QualityValueFitSummary | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.provenance_id, "provenance_id")
        require_non_empty(self.source_id, "source_id")
        require_non_empty(self.subject_id, "subject_id")
        require_non_empty(self.summary, "summary")
        if self.source_category not in schema.SOURCE_CATEGORIES:
            raise ValueError(f"source_category must be one of {schema.SOURCE_CATEGORIES}")
        if self.subject_kind not in schema.PROVENANCE_SUBJECT_KINDS:
            raise ValueError(f"subject_kind must be one of {schema.PROVENANCE_SUBJECT_KINDS}")
        if self.contribution_kind not in schema.CONTRIBUTION_KINDS:
            raise ValueError(f"contribution_kind must be one of {schema.CONTRIBUTION_KINDS}")
        require_optional_non_empty(self.locator or None, "locator")
        require_optional_non_empty(self.captured_at or None, "captured_at")
        if self.freshness_days_at_capture is not None:
            require_non_negative(self.freshness_days_at_capture, "freshness_days_at_capture")
        if self.trust_snapshot is not None and not isinstance(
            self.trust_snapshot, SourceTrustSignals
        ):
            raise ValueError("trust_snapshot must be a SourceTrustSignals when provided")
        if self.quality_value_fit is not None and not isinstance(
            self.quality_value_fit, QualityValueFitSummary
        ):
            raise ValueError("quality_value_fit must be a QualityValueFitSummary when provided")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
