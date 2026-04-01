"""Shared explanation records for ranking and route-search outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from trip_planner._validators import require_non_empty, require_strings

EXPLANATION_RECORD_TYPES: tuple[str, ...] = (
    "summary",
    "promotion",
    "penalty",
    "risk",
    "confidence",
)
EXPLANATION_TARGET_KINDS: tuple[str, ...] = ("item", "bundle", "route")


def _require_string_mapping(values: dict[str, str], field_name: str) -> None:
    if any(not isinstance(key, str) or not key for key in values):
        raise ValueError(f"{field_name} must use non-empty string keys")
    if any(not isinstance(value, str) or not value for value in values.values()):
        raise ValueError(f"{field_name} must use non-empty string values")


@dataclass(slots=True)
class ExplanationRecord:
    explanation_id: str
    record_type: str = "summary"
    target_kind: str = "item"
    target_id: str = ""
    headline: str = ""
    summary: str = ""
    factor_keys: list[str] = field(default_factory=list)
    machine_context: dict[str, str] = field(default_factory=dict)
    human_summary: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.explanation_id, "explanation_id")
        require_non_empty(self.target_id, "target_id")
        require_non_empty(self.headline, "headline")
        require_non_empty(self.summary, "summary")
        if self.record_type not in EXPLANATION_RECORD_TYPES:
            raise ValueError(f"record_type must be one of {EXPLANATION_RECORD_TYPES}")
        if self.target_kind not in EXPLANATION_TARGET_KINDS:
            raise ValueError(f"target_kind must be one of {EXPLANATION_TARGET_KINDS}")
        require_strings(self.factor_keys, "factor_keys")
        _require_string_mapping(self.machine_context, "machine_context")
        require_strings(self.human_summary, "human_summary")
        require_strings(self.source_refs, "source_refs")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
