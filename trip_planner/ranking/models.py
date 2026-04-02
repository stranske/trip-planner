"""Canonical ranking-result contracts shared by later ranking layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._option_contracts import (
    COMPARISON_DIRECTIONS,
    OPTION_SET_PURPOSES,
    OPTION_SET_SCOPES,
    ComparisonAxis,
    MoneyRange,
    Option,
    OptionCostSummary,
    OptionQualitySummary,
)
from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_probability,
    require_strings,
)

from .explanations import ExplanationRecord

SCHEMA_VERSION = "0.1.0"
RANK_RESULT_KINDS: tuple[str, ...] = ("item", "bundle", "route")
ADJUSTMENT_KINDS: tuple[str, ...] = ("penalty", "bonus", "missing_data")
RISK_SEVERITIES: tuple[str, ...] = ("info", "warning", "critical")


def _optional_list_field(payload: dict[str, Any], field_name: str) -> list[Any]:
    value = payload.get(field_name, [])
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list when provided")
    return value


def _optional_mapping_field(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping when provided")
    return value


def _parse_money_range(payload: dict[str, Any] | None) -> MoneyRange | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("money range payload must be a mapping when provided")
    return MoneyRange(**payload)


def _parse_option(payload: dict[str, Any]) -> Option:
    cost_payload = _optional_mapping_field(payload, "cost_summary")
    quality_payload = _optional_mapping_field(payload, "quality_summary")
    return Option(
        option_id=payload["option_id"],
        kind=payload["kind"],
        label=payload["label"],
        summary=payload.get("summary", ""),
        fit_signals=dict(payload.get("fit_signals", {})),
        cost_summary=OptionCostSummary(
            total=_parse_money_range(cost_payload.get("total")),
            per_unit=_parse_money_range(cost_payload.get("per_unit")),
            notes=_optional_list_field(cost_payload, "notes"),
        ),
        quality_summary=OptionQualitySummary(
            quality_signal=quality_payload.get("quality_signal"),
            value_signal=quality_payload.get("value_signal"),
            fit_signal=quality_payload.get("fit_signal"),
            notes=_optional_list_field(quality_payload, "notes"),
        ),
        drawbacks=_optional_list_field(payload, "drawbacks"),
        booking_links=_optional_list_field(payload, "booking_links"),
        source_refs=_optional_list_field(payload, "source_refs"),
        supporting_place_ids=_optional_list_field(payload, "supporting_place_ids"),
        explanation=_optional_list_field(payload, "explanation"),
    )


@dataclass(slots=True)
class ScoreContribution:
    contribution_id: str
    label: str
    axis_key: str = ""
    direction: str = "contextual"
    raw_value: float | None = None
    normalized_signal: float | None = None
    weighted_impact: float = 0.0
    summary: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.contribution_id, "contribution_id")
        require_non_empty(self.label, "label")
        if self.direction not in COMPARISON_DIRECTIONS:
            raise ValueError(f"direction must be one of {COMPARISON_DIRECTIONS}")
        if self.normalized_signal is not None:
            require_probability(self.normalized_signal, "normalized_signal")
        require_strings(self.evidence_refs, "evidence_refs")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScoreAdjustment:
    adjustment_id: str
    label: str
    kind: str
    amount: float
    reason_code: str
    summary: str = ""
    affected_factor_keys: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.adjustment_id, "adjustment_id")
        require_non_empty(self.label, "label")
        require_non_empty(self.reason_code, "reason_code")
        require_non_negative(self.amount, "amount")
        if self.kind not in ADJUSTMENT_KINDS:
            raise ValueError(f"kind must be one of {ADJUSTMENT_KINDS}")
        require_strings(self.affected_factor_keys, "affected_factor_keys")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScoreConfidenceSummary:
    overall_confidence: float | None = None
    input_coverage: float | None = None
    data_freshness: float | None = None
    scoring_stability: float | None = None
    low_confidence_flags: list[str] = field(default_factory=list)
    missing_data_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "overall_confidence",
            "input_coverage",
            "data_freshness",
            "scoring_stability",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        require_strings(self.low_confidence_flags, "low_confidence_flags")
        require_strings(self.missing_data_fields, "missing_data_fields")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RiskFlag:
    risk_id: str
    code: str
    severity: str = "warning"
    summary: str = ""
    blocking: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.risk_id, "risk_id")
        require_non_empty(self.code, "code")
        require_non_empty(self.summary, "summary")
        if self.severity not in RISK_SEVERITIES:
            raise ValueError(f"severity must be one of {RISK_SEVERITIES}")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScoreBreakdown:
    baseline_score: float = 0.0
    component_contributions: list[ScoreContribution] = field(default_factory=list)
    penalties: list[ScoreAdjustment] = field(default_factory=list)
    bonuses: list[ScoreAdjustment] = field(default_factory=list)
    missing_data_penalties: list[ScoreAdjustment] = field(default_factory=list)
    final_score: float = 0.0
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if any(
            not isinstance(item, ScoreContribution)
            for item in self.component_contributions
        ):
            raise ValueError(
                "component_contributions must contain ScoreContribution instances"
            )
        if any(not isinstance(item, ScoreAdjustment) for item in self.penalties):
            raise ValueError("penalties must contain ScoreAdjustment instances")
        if any(not isinstance(item, ScoreAdjustment) for item in self.bonuses):
            raise ValueError("bonuses must contain ScoreAdjustment instances")
        if any(
            not isinstance(item, ScoreAdjustment)
            for item in self.missing_data_penalties
        ):
            raise ValueError(
                "missing_data_penalties must contain ScoreAdjustment instances"
            )
        if any(item.kind != "penalty" for item in self.penalties):
            raise ValueError("penalties must only contain penalty adjustments")
        if any(item.kind != "bonus" for item in self.bonuses):
            raise ValueError("bonuses must only contain bonus adjustments")
        if any(item.kind != "missing_data" for item in self.missing_data_penalties):
            raise ValueError(
                "missing_data_penalties must only contain missing_data adjustments"
            )
        require_strings(self.notes, "notes")

        computed_score = self.baseline_score
        computed_score += sum(
            item.weighted_impact for item in self.component_contributions
        )
        computed_score += sum(item.amount for item in self.bonuses)
        computed_score -= sum(item.amount for item in self.penalties)
        computed_score -= sum(item.amount for item in self.missing_data_penalties)
        if abs(self.final_score - computed_score) > 1e-9:
            raise ValueError("final_score must match the summed score breakdown")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RankedResult:
    result_id: str
    result_kind: str
    rank: int
    score: float
    target_option: Option | None = None
    target_bundle_id: str | None = None
    supporting_option_ids: list[str] = field(default_factory=list)
    supporting_destination_ids: list[str] = field(default_factory=list)
    route_sequence: list[str] = field(default_factory=list)
    score_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    confidence_summary: ScoreConfidenceSummary = field(
        default_factory=ScoreConfidenceSummary
    )
    explanation_records: list[ExplanationRecord] = field(default_factory=list)
    unresolved_risks: list[RiskFlag] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.result_id, "result_id")
        require_non_negative(self.rank, "rank")
        if self.rank <= 0:
            raise ValueError("rank must be positive")
        if self.result_kind not in RANK_RESULT_KINDS:
            raise ValueError(f"result_kind must be one of {RANK_RESULT_KINDS}")
        if self.target_option is not None and not isinstance(
            self.target_option, Option
        ):
            raise ValueError("target_option must be an Option when provided")
        if not isinstance(self.score_breakdown, ScoreBreakdown):
            raise ValueError("score_breakdown must be a ScoreBreakdown")
        if not isinstance(self.confidence_summary, ScoreConfidenceSummary):
            raise ValueError("confidence_summary must be a ScoreConfidenceSummary")
        if any(
            not isinstance(item, ExplanationRecord) for item in self.explanation_records
        ):
            raise ValueError(
                "explanation_records must contain ExplanationRecord instances"
            )
        if any(not isinstance(item, RiskFlag) for item in self.unresolved_risks):
            raise ValueError("unresolved_risks must contain RiskFlag instances")
        require_strings(self.supporting_option_ids, "supporting_option_ids")
        require_strings(self.supporting_destination_ids, "supporting_destination_ids")
        require_strings(self.route_sequence, "route_sequence")
        require_strings(self.source_refs, "source_refs")
        require_strings(self.notes, "notes")
        if self.score_breakdown.final_score != self.score:
            raise ValueError("score must match score_breakdown.final_score")
        if not self.explanation_records:
            raise ValueError(
                "explanation_records must contain at least one ExplanationRecord"
            )

        if self.result_kind == "item":
            if self.target_option is None:
                raise ValueError("item results must provide target_option")
            if self.target_bundle_id is not None:
                raise ValueError("item results cannot provide target_bundle_id")
        else:
            if not self.target_bundle_id:
                raise ValueError(
                    "bundle and route results must provide target_bundle_id"
                )
            if self.result_kind == "route" and not self.route_sequence:
                raise ValueError("route results must provide route_sequence")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RankedResult":
        target_option_payload = payload.get("target_option")
        return cls(
            result_id=payload["result_id"],
            result_kind=payload["result_kind"],
            rank=payload["rank"],
            score=payload["score"],
            target_option=(
                _parse_option(target_option_payload)
                if target_option_payload is not None
                else None
            ),
            target_bundle_id=payload.get("target_bundle_id"),
            supporting_option_ids=_optional_list_field(
                payload, "supporting_option_ids"
            ),
            supporting_destination_ids=_optional_list_field(
                payload, "supporting_destination_ids"
            ),
            route_sequence=_optional_list_field(payload, "route_sequence"),
            score_breakdown=ScoreBreakdown(
                baseline_score=_optional_mapping_field(payload, "score_breakdown").get(
                    "baseline_score", 0.0
                ),
                component_contributions=[
                    ScoreContribution(**item)
                    for item in _optional_list_field(
                        _optional_mapping_field(payload, "score_breakdown"),
                        "component_contributions",
                    )
                ],
                penalties=[
                    ScoreAdjustment(**item)
                    for item in _optional_list_field(
                        _optional_mapping_field(payload, "score_breakdown"), "penalties"
                    )
                ],
                bonuses=[
                    ScoreAdjustment(**item)
                    for item in _optional_list_field(
                        _optional_mapping_field(payload, "score_breakdown"), "bonuses"
                    )
                ],
                missing_data_penalties=[
                    ScoreAdjustment(**item)
                    for item in _optional_list_field(
                        _optional_mapping_field(payload, "score_breakdown"),
                        "missing_data_penalties",
                    )
                ],
                final_score=_optional_mapping_field(payload, "score_breakdown").get(
                    "final_score", 0.0
                ),
                notes=_optional_list_field(
                    _optional_mapping_field(payload, "score_breakdown"), "notes"
                ),
            ),
            confidence_summary=ScoreConfidenceSummary(
                **_optional_mapping_field(payload, "confidence_summary")
            ),
            explanation_records=[
                ExplanationRecord(**item)
                for item in _optional_list_field(payload, "explanation_records")
            ],
            unresolved_risks=[
                RiskFlag(**item)
                for item in _optional_list_field(payload, "unresolved_risks")
            ],
            source_refs=_optional_list_field(payload, "source_refs"),
            notes=_optional_list_field(payload, "notes"),
        )


@dataclass(slots=True)
class RankedResultSet:
    result_set_id: str
    trip_id: str
    purpose: str
    scope: str
    title: str
    results: list[RankedResult]
    comparison_axes: list[ComparisonAxis] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.result_set_id, "result_set_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.title, "title")
        if self.purpose not in OPTION_SET_PURPOSES:
            raise ValueError(f"purpose must be one of {OPTION_SET_PURPOSES}")
        if self.scope not in OPTION_SET_SCOPES:
            raise ValueError(f"scope must be one of {OPTION_SET_SCOPES}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if not self.results:
            raise ValueError("results must contain at least one RankedResult")
        if any(not isinstance(item, RankedResult) for item in self.results):
            raise ValueError("results must contain RankedResult instances")
        if any(not isinstance(item, ComparisonAxis) for item in self.comparison_axes):
            raise ValueError("comparison_axes must contain ComparisonAxis instances")
        require_strings(self.explanation, "explanation")
        require_strings(self.source_refs, "source_refs")

        ranks = [item.rank for item in self.results]
        if len(set(ranks)) != len(ranks):
            raise ValueError("results must use unique ranks")
        result_ids = [item.result_id for item in self.results]
        if len(set(result_ids)) != len(result_ids):
            raise ValueError("results must use unique result_ids")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RankedResultSet":
        return cls(
            result_set_id=payload["result_set_id"],
            trip_id=payload["trip_id"],
            purpose=payload["purpose"],
            scope=payload["scope"],
            title=payload["title"],
            results=[
                RankedResult.from_dict(item)
                for item in _optional_list_field(payload, "results")
            ],
            comparison_axes=[
                ComparisonAxis(**item)
                for item in _optional_list_field(payload, "comparison_axes")
            ],
            explanation=_optional_list_field(payload, "explanation"),
            source_refs=_optional_list_field(payload, "source_refs"),
            schema_version=payload.get("schema_version", SCHEMA_VERSION),
        )
