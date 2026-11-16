"""Shared explanation records for ranking and route-search outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from trip_planner._validators import require_non_empty, require_strings
from trip_planner.sources.quality import SourceConfidenceSummary

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


def build_source_confidence_explanation(
    *,
    target_id: str,
    target_kind: str = "item",
    summary: SourceConfidenceSummary,
    source_refs: list[str] | None = None,
) -> ExplanationRecord:
    """Build a ``confidence`` ExplanationRecord from a fused source summary.

    Ranking engines and planner-tool consumers can call this when a candidate
    or option carries a :class:`SourceConfidenceSummary` so that traveler-facing
    explanations include source-confidence language alongside the existing
    ranking-confidence record.
    """

    if not isinstance(summary, SourceConfidenceSummary):
        raise ValueError("summary must be a SourceConfidenceSummary")
    if target_kind not in EXPLANATION_TARGET_KINDS:
        raise ValueError(f"target_kind must be one of {EXPLANATION_TARGET_KINDS}")

    machine_context: dict[str, str] = {
        "source_confidence": f"{summary.confidence:.2f}",
        "source_confidence_label": summary.confidence_label,
        "contributing_source_count": str(summary.contributing_source_count),
        "freshness": summary.freshness_summary,
        "conflict_detected": "true" if summary.conflict_detected else "false",
    }

    refs: list[str] = []
    seen: set[str] = set()
    for entry in source_refs or []:
        if entry and entry not in seen:
            refs.append(entry)
            seen.add(entry)
    for score in summary.per_source_scores:
        if score.source_id not in seen:
            refs.append(score.source_id)
            seen.add(score.source_id)
    refs = refs[:6]

    factor_keys = ["source_confidence", *summary.tags[:4]]

    headline_map = {
        "very_high": "Strong source coverage",
        "high": "Solid source coverage",
        "moderate": "Mixed source coverage",
        "uncertain": "Uncertain source coverage",
        "sparse": "Sparse source coverage",
    }
    headline = headline_map.get(summary.confidence_label, "Source confidence")

    summary_text = " ".join(summary.explanation_fragments) or (
        "Source confidence is summarized from the contributing source records."
    )

    return ExplanationRecord(
        explanation_id=f"source-confidence:{target_id}",
        record_type="confidence",
        target_kind=target_kind,
        target_id=target_id,
        headline=headline,
        summary=summary_text,
        factor_keys=factor_keys,
        machine_context=machine_context,
        human_summary=list(summary.explanation_fragments),
        source_refs=refs,
    )
