"""Canonical mixed inventory bundle contracts for normalized option assembly."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_optional_non_empty,
    require_probability,
    require_strings,
)
from trip_planner._option_contracts import (
    OPTION_SET_PURPOSES,
    MoneyRange,
    Option,
    OptionCostSummary,
    OptionQualitySummary,
)
from trip_planner.sources.models import QualityValueFitSummary, SourceRecord, SourceTrustSignals

from .activities import ActivityOption
from .destinations import Destination
from .lodging import LodgingOption
from .transport import TransportOption

SCHEMA_VERSION = "0.1.0"

BUNDLE_CONTEXTS: tuple[str, ...] = (
    "lodging_only",
    "transport_lodging",
    "route_level",
    "activity_cluster",
    "mixed",
)


def _require_string_list(values: Any, field_name: str) -> None:
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of non-empty strings")
    require_strings(values, field_name)


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


def _parse_money_range(payload: dict[str, Any] | None, field_name: str) -> MoneyRange | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name} must be a mapping when provided")
    return MoneyRange(**payload)


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _parse_source_record(payload: dict[str, Any]) -> SourceRecord:
    trust_payload = payload.get("trust_signals") or {}
    quality_payload = payload.get("quality_summary") or {}
    return SourceRecord(
        **{
            **payload,
            "trust_signals": SourceTrustSignals(**trust_payload),
            "quality_summary": QualityValueFitSummary(**quality_payload),
        }
    )


@dataclass(slots=True)
class BundleProvenanceSummary:
    source_refs: list[str] = field(default_factory=list)
    booking_links: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_string_list(self.source_refs, "source_refs")
        _require_string_list(self.booking_links, "booking_links")
        _require_string_list(self.notes, "notes")
        if len(set(self.source_refs)) != len(self.source_refs):
            raise ValueError("source_refs must not contain duplicates")
        if len(set(self.booking_links)) != len(self.booking_links):
            raise ValueError("booking_links must not contain duplicates")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BundleQualityValueFitSummary:
    quality_signal: float | None = None
    value_signal: float | None = None
    fit_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("quality_signal", "value_signal", "fit_signal"):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BundleCompositionSummary:
    sequence_index: int | None = None
    assembly_role: str = ""
    primary_destination_id: str = ""
    component_option_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.sequence_index is not None:
            require_non_negative(self.sequence_index, "sequence_index")
        require_optional_non_empty(self.assembly_role or None, "assembly_role")
        require_optional_non_empty(self.primary_destination_id or None, "primary_destination_id")
        _require_string_list(self.component_option_ids, "component_option_ids")
        _require_string_list(self.notes, "notes")
        if len(set(self.component_option_ids)) != len(self.component_option_ids):
            raise ValueError("component_option_ids must not contain duplicates")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BundleFeasibility:
    available: bool = True
    internally_consistent: bool = True
    blocking_reasons: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    accessibility_notes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_string_list(self.blocking_reasons, "blocking_reasons")
        _require_string_list(self.dependencies, "dependencies")
        _require_string_list(self.accessibility_notes, "accessibility_notes")
        _require_string_list(self.notes, "notes")
        if (not self.available or not self.internally_consistent) and not self.blocking_reasons:
            raise ValueError(
                "blocking_reasons must describe why the bundle is unavailable or inconsistent"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RouteCoherenceSummary:
    overall_signal: float | None = None
    route_shape: str = ""
    movement_summary: str = ""
    destination_sequence: list[str] = field(default_factory=list)
    base_change_count: int = 0
    cohesion_signal: float | None = None
    recovery_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("overall_signal", "cohesion_signal", "recovery_signal"):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        require_optional_non_empty(self.route_shape or None, "route_shape")
        require_optional_non_empty(self.movement_summary or None, "movement_summary")
        require_non_negative(self.base_change_count, "base_change_count")
        _require_string_list(self.destination_sequence, "destination_sequence")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScheduleFitSummary:
    overall_signal: float | None = None
    pacing_signal: float | None = None
    arrival_alignment_signal: float | None = None
    recovery_window_signal: float | None = None
    buffer_signal: float | None = None
    overcommitment_risk_signal: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "overall_signal",
            "pacing_signal",
            "arrival_alignment_signal",
            "recovery_window_signal",
            "buffer_signal",
            "overcommitment_risk_signal",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BudgetPostureSummary:
    estimated_total: MoneyRange | None = None
    lodging_total: MoneyRange | None = None
    transport_total: MoneyRange | None = None
    activity_total: MoneyRange | None = None
    overall_signal: float | None = None
    within_target_budget: bool | None = None
    stretch_required: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "estimated_total",
            "lodging_total",
            "transport_total",
            "activity_total",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, MoneyRange):
                raise ValueError(f"{field_name} must be a MoneyRange when provided")
        if self.overall_signal is not None:
            require_probability(self.overall_signal, "overall_signal")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BundleExplanation:
    headline: str = ""
    strengths: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_optional_non_empty(self.headline or None, "headline")
        _require_string_list(self.strengths, "strengths")
        _require_string_list(self.tradeoffs, "tradeoffs")
        _require_string_list(self.evidence, "evidence")
        _require_string_list(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class InventoryBundle:
    bundle_id: str
    title: str
    bundle_context: str = "mixed"
    destinations: list[Destination] = field(default_factory=list)
    lodging_options: list[LodgingOption] = field(default_factory=list)
    transport_options: list[TransportOption] = field(default_factory=list)
    activity_options: list[ActivityOption] = field(default_factory=list)
    composition_summary: BundleCompositionSummary = field(default_factory=BundleCompositionSummary)
    provenance_summary: BundleProvenanceSummary = field(default_factory=BundleProvenanceSummary)
    quality_value_fit: BundleQualityValueFitSummary = field(
        default_factory=BundleQualityValueFitSummary
    )
    source_records: list[SourceRecord] = field(default_factory=list)
    feasibility: BundleFeasibility = field(default_factory=BundleFeasibility)
    explanation: BundleExplanation = field(default_factory=BundleExplanation)
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.bundle_id, "bundle_id")
        require_non_empty(self.title, "title")
        if self.bundle_context not in BUNDLE_CONTEXTS:
            raise ValueError(f"bundle_context must be one of {BUNDLE_CONTEXTS}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if any(not isinstance(item, Destination) for item in self.destinations):
            raise ValueError("destinations must contain Destination instances")
        if any(not isinstance(item, LodgingOption) for item in self.lodging_options):
            raise ValueError("lodging_options must contain LodgingOption instances")
        if any(not isinstance(item, TransportOption) for item in self.transport_options):
            raise ValueError("transport_options must contain TransportOption instances")
        if any(not isinstance(item, ActivityOption) for item in self.activity_options):
            raise ValueError("activity_options must contain ActivityOption instances")
        if not isinstance(self.composition_summary, BundleCompositionSummary):
            raise ValueError("composition_summary must be a BundleCompositionSummary")
        if not isinstance(self.provenance_summary, BundleProvenanceSummary):
            raise ValueError("provenance_summary must be a BundleProvenanceSummary")
        if not isinstance(self.quality_value_fit, BundleQualityValueFitSummary):
            raise ValueError("quality_value_fit must be a BundleQualityValueFitSummary")
        if any(not isinstance(item, SourceRecord) for item in self.source_records):
            raise ValueError("source_records must contain SourceRecord instances")
        if not isinstance(self.feasibility, BundleFeasibility):
            raise ValueError("feasibility must be a BundleFeasibility")
        if not isinstance(self.explanation, BundleExplanation):
            raise ValueError("explanation must be a BundleExplanation")
        if not (self.lodging_options or self.transport_options or self.activity_options):
            raise ValueError(
                "InventoryBundle must include at least one lodging, transport, or activity option"
            )
        _require_string_list(self.tags, "tags")
        _require_string_list(self.notes, "notes")
        represented_destination_ids = {item.destination_id for item in self.destinations}
        referenced_destination_ids = {item.destination_id for item in self.lodging_options} | {
            item.destination_id for item in self.activity_options
        }
        transport_destination_ids = {
            endpoint
            for item in self.transport_options
            for endpoint in (item.origin_id, item.destination_id)
        }
        if referenced_destination_ids and not represented_destination_ids:
            raise ValueError(
                "destinations must include each destination referenced by lodging or activity options"
            )
        if represented_destination_ids and not referenced_destination_ids.issubset(
            represented_destination_ids
        ):
            raise ValueError(
                "destinations must include each destination referenced by lodging or activity options"
            )
        if transport_destination_ids and not represented_destination_ids:
            raise ValueError(
                "destinations must include each origin_id and destination_id referenced by transport options"
            )
        if represented_destination_ids and not transport_destination_ids.issubset(
            represented_destination_ids
        ):
            raise ValueError(
                "destinations must include each origin_id and destination_id referenced by transport options"
            )
        included_option_ids = self.option_ids
        if self.composition_summary.component_option_ids and set(
            self.composition_summary.component_option_ids
        ) != set(included_option_ids):
            raise ValueError(
                "composition_summary.component_option_ids must match the options included in the bundle"
            )
        if (
            self.composition_summary.primary_destination_id
            and self.composition_summary.primary_destination_id not in represented_destination_ids
        ):
            raise ValueError(
                "composition_summary.primary_destination_id must reference a bundle destination"
            )
        nested_source_refs = set(self._aggregate_source_refs())
        if not set(self.provenance_summary.source_refs).issubset(nested_source_refs):
            raise ValueError(
                "provenance_summary.source_refs must be drawn from the included destination and option source refs"
            )
        nested_booking_links = set(self._aggregate_booking_links())
        if not set(self.provenance_summary.booking_links).issubset(nested_booking_links):
            raise ValueError(
                "provenance_summary.booking_links must be drawn from the included option booking links"
            )

    @property
    def destination_ids(self) -> list[str]:
        return [item.destination_id for item in self.destinations]

    @property
    def option_ids(self) -> list[str]:
        return _dedupe_strings(
            [item.option_id for item in self.lodging_options]
            + [item.option_id for item in self.transport_options]
            + [item.option_id for item in self.activity_options]
        )

    def _aggregate_booking_links(self) -> list[str]:
        values: list[str] = []
        for lodging_option in self.lodging_options:
            values.extend(lodging_option.booking_links)
        for transport_option in self.transport_options:
            values.extend(transport_option.booking_links)
        for activity_option in self.activity_options:
            values.extend(activity_option.booking_links)
        return _dedupe_strings(values)

    def _aggregate_source_refs(self) -> list[str]:
        values = [
            item.provenance_id
            for destination in self.destinations
            for item in destination.source_refs
        ]
        for lodging_option in self.lodging_options:
            values.extend(item.provenance_id for item in lodging_option.source_refs)
        for transport_option in self.transport_options:
            values.extend(item.provenance_id for item in transport_option.source_refs)
        for activity_option in self.activity_options:
            values.extend(item.provenance_id for item in activity_option.source_refs)
        return _dedupe_strings(values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InventoryBundle":
        return cls(
            bundle_id=payload["bundle_id"],
            title=payload["title"],
            bundle_context=payload.get("bundle_context", "mixed"),
            destinations=[
                Destination.from_dict(item)
                for item in _optional_list_field(payload, "destinations")
            ],
            lodging_options=[
                LodgingOption.from_dict(item)
                for item in _optional_list_field(payload, "lodging_options")
            ],
            transport_options=[
                TransportOption.from_dict(item)
                for item in _optional_list_field(payload, "transport_options")
            ],
            activity_options=[
                ActivityOption.from_dict(item)
                for item in _optional_list_field(payload, "activity_options")
            ],
            composition_summary=BundleCompositionSummary(
                **_optional_mapping_field(payload, "composition_summary")
            ),
            provenance_summary=BundleProvenanceSummary(
                **_optional_mapping_field(payload, "provenance_summary")
            ),
            quality_value_fit=BundleQualityValueFitSummary(
                **_optional_mapping_field(payload, "quality_value_fit")
            ),
            source_records=[
                _parse_source_record(item)
                for item in _optional_list_field(payload, "source_records")
            ],
            feasibility=BundleFeasibility(**_optional_mapping_field(payload, "feasibility")),
            explanation=BundleExplanation(**_optional_mapping_field(payload, "explanation")),
            summary=payload.get("summary", ""),
            tags=_optional_list_field(payload, "tags"),
            notes=_optional_list_field(payload, "notes"),
            schema_version=payload.get("schema_version", SCHEMA_VERSION),
        )


@dataclass(slots=True)
class MixedOption:
    option_id: str
    trip_id: str
    title: str
    bundles: list[InventoryBundle]
    supported_purposes: list[str] = field(
        default_factory=lambda: ["profile_learning", "inventory_narrowing"]
    )
    route_coherence: RouteCoherenceSummary = field(default_factory=RouteCoherenceSummary)
    schedule_fit: ScheduleFitSummary = field(default_factory=ScheduleFitSummary)
    budget_posture: BudgetPostureSummary = field(default_factory=BudgetPostureSummary)
    composition_summary: BundleCompositionSummary = field(default_factory=BundleCompositionSummary)
    provenance_summary: BundleProvenanceSummary = field(default_factory=BundleProvenanceSummary)
    quality_value_fit: BundleQualityValueFitSummary = field(
        default_factory=BundleQualityValueFitSummary
    )
    explanation: BundleExplanation = field(default_factory=BundleExplanation)
    comparison_label: str = ""
    summary: str = ""
    booking_links: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.option_id, "option_id")
        require_non_empty(self.trip_id, "trip_id")
        require_non_empty(self.title, "title")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if not self.bundles:
            raise ValueError("bundles must contain at least one InventoryBundle")
        if any(not isinstance(item, InventoryBundle) for item in self.bundles):
            raise ValueError("bundles must contain InventoryBundle instances")
        if not isinstance(self.route_coherence, RouteCoherenceSummary):
            raise ValueError("route_coherence must be a RouteCoherenceSummary")
        if not isinstance(self.schedule_fit, ScheduleFitSummary):
            raise ValueError("schedule_fit must be a ScheduleFitSummary")
        if not isinstance(self.budget_posture, BudgetPostureSummary):
            raise ValueError("budget_posture must be a BudgetPostureSummary")
        if not isinstance(self.composition_summary, BundleCompositionSummary):
            raise ValueError("composition_summary must be a BundleCompositionSummary")
        if not isinstance(self.provenance_summary, BundleProvenanceSummary):
            raise ValueError("provenance_summary must be a BundleProvenanceSummary")
        if not isinstance(self.quality_value_fit, BundleQualityValueFitSummary):
            raise ValueError("quality_value_fit must be a BundleQualityValueFitSummary")
        if not isinstance(self.explanation, BundleExplanation):
            raise ValueError("explanation must be a BundleExplanation")
        _require_string_list(self.supported_purposes, "supported_purposes")
        invalid_purposes = [
            purpose for purpose in self.supported_purposes if purpose not in OPTION_SET_PURPOSES
        ]
        if invalid_purposes:
            raise ValueError(f"supported_purposes must contain only {OPTION_SET_PURPOSES}")
        if len(set(self.supported_purposes)) != len(self.supported_purposes):
            raise ValueError("supported_purposes must not contain duplicates")
        require_optional_non_empty(self.comparison_label or None, "comparison_label")
        _require_string_list(self.booking_links, "booking_links")
        _require_string_list(self.source_refs, "source_refs")
        _require_string_list(self.tags, "tags")
        _require_string_list(self.notes, "notes")
        bundle_ids = [item.bundle_id for item in self.bundles]
        if len(set(bundle_ids)) != len(bundle_ids):
            raise ValueError("bundles must not contain duplicate bundle_id values")
        if self.composition_summary.component_option_ids and set(
            self.composition_summary.component_option_ids
        ) != {option_id for bundle in self.bundles for option_id in bundle.option_ids}:
            raise ValueError(
                "composition_summary.component_option_ids must match the options included across the bundles"
            )
        if self.composition_summary.primary_destination_id and (
            self.composition_summary.primary_destination_id
            not in {
                destination_id
                for bundle in self.bundles
                for destination_id in bundle.destination_ids
            }
        ):
            raise ValueError(
                "composition_summary.primary_destination_id must reference a destination in the included bundles"
            )
        if self.route_coherence.destination_sequence:
            bundle_destination_ids = {
                destination_id
                for bundle in self.bundles
                for destination_id in bundle.destination_ids
            }
            if not bundle_destination_ids.issubset(set(self.route_coherence.destination_sequence)):
                raise ValueError(
                    "route_coherence.destination_sequence must cover each destination in the included bundles"
                )
        aggregated_source_refs = set(self._aggregate_source_refs())
        explicit_source_refs = set(self.source_refs) | set(self.provenance_summary.source_refs)
        if not explicit_source_refs.issubset(aggregated_source_refs):
            raise ValueError(
                "source_refs and provenance_summary.source_refs must be drawn from the included bundles"
            )
        aggregated_booking_links = set(self._aggregate_booking_links())
        explicit_booking_links = set(self.booking_links) | set(
            self.provenance_summary.booking_links
        )
        if not explicit_booking_links.issubset(aggregated_booking_links):
            raise ValueError(
                "booking_links and provenance_summary.booking_links must be drawn from the included bundles"
            )

    def _aggregate_booking_links(self) -> list[str]:
        values: list[str] = []
        for bundle in self.bundles:
            for lodging_option in bundle.lodging_options:
                values.extend(lodging_option.booking_links)
            for transport_option in bundle.transport_options:
                values.extend(transport_option.booking_links)
            for activity_option in bundle.activity_options:
                values.extend(activity_option.booking_links)
        return _dedupe_strings(values)

    def _aggregate_source_refs(self) -> list[str]:
        values: list[str] = []
        for bundle in self.bundles:
            for destination in bundle.destinations:
                values.extend(item.provenance_id for item in destination.source_refs)
            for lodging_option in bundle.lodging_options:
                values.extend(item.provenance_id for item in lodging_option.source_refs)
            for transport_option in bundle.transport_options:
                values.extend(item.provenance_id for item in transport_option.source_refs)
            for activity_option in bundle.activity_options:
                values.extend(item.provenance_id for item in activity_option.source_refs)
        return _dedupe_strings(values)

    def _aggregate_destination_ids(self) -> list[str]:
        return _dedupe_strings(
            [destination_id for bundle in self.bundles for destination_id in bundle.destination_ids]
        )

    def to_option(self) -> Option:
        explanation = list(self.explanation.strengths)
        if self.explanation.headline:
            explanation.insert(0, self.explanation.headline)
        return Option(
            option_id=self.option_id,
            kind="mixed",
            label=self.title,
            summary=self.summary,
            fit_signals={
                key: value
                for key, value in {
                    "route_coherence": self.route_coherence.overall_signal,
                    "schedule_fit": self.schedule_fit.overall_signal,
                    "budget_posture": self.budget_posture.overall_signal,
                }.items()
                if value is not None
            },
            cost_summary=OptionCostSummary(total=self.budget_posture.estimated_total),
            quality_summary=OptionQualitySummary(
                quality_signal=self.quality_value_fit.quality_signal
                or self.route_coherence.overall_signal,
                value_signal=self.quality_value_fit.value_signal
                or self.budget_posture.overall_signal,
                fit_signal=self.quality_value_fit.fit_signal or self.schedule_fit.overall_signal,
            ),
            drawbacks=_dedupe_strings(
                self.explanation.tradeoffs
                + [
                    reason
                    for bundle in self.bundles
                    for reason in bundle.feasibility.blocking_reasons
                ]
            ),
            booking_links=self._aggregate_booking_links(),
            source_refs=self._aggregate_source_refs(),
            supporting_place_ids=(
                self.route_coherence.destination_sequence or self._aggregate_destination_ids()
            ),
            explanation=explanation,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MixedOption":
        budget_payload = _optional_mapping_field(payload, "budget_posture")
        return cls(
            option_id=payload["option_id"],
            trip_id=payload["trip_id"],
            title=payload["title"],
            bundles=[
                InventoryBundle.from_dict(item) for item in _optional_list_field(payload, "bundles")
            ],
            supported_purposes=_optional_list_field(payload, "supported_purposes")
            or ["profile_learning", "inventory_narrowing"],
            route_coherence=RouteCoherenceSummary(
                **_optional_mapping_field(payload, "route_coherence")
            ),
            schedule_fit=ScheduleFitSummary(**_optional_mapping_field(payload, "schedule_fit")),
            budget_posture=BudgetPostureSummary(
                estimated_total=_parse_money_range(
                    budget_payload.get("estimated_total"),
                    "budget_posture.estimated_total",
                ),
                lodging_total=_parse_money_range(
                    budget_payload.get("lodging_total"),
                    "budget_posture.lodging_total",
                ),
                transport_total=_parse_money_range(
                    budget_payload.get("transport_total"),
                    "budget_posture.transport_total",
                ),
                activity_total=_parse_money_range(
                    budget_payload.get("activity_total"),
                    "budget_posture.activity_total",
                ),
                overall_signal=budget_payload.get("overall_signal"),
                within_target_budget=budget_payload.get("within_target_budget"),
                stretch_required=budget_payload.get("stretch_required", False),
                notes=budget_payload.get("notes", []),
            ),
            composition_summary=BundleCompositionSummary(
                **_optional_mapping_field(payload, "composition_summary")
            ),
            provenance_summary=BundleProvenanceSummary(
                **_optional_mapping_field(payload, "provenance_summary")
            ),
            quality_value_fit=BundleQualityValueFitSummary(
                **_optional_mapping_field(payload, "quality_value_fit")
            ),
            explanation=BundleExplanation(**_optional_mapping_field(payload, "explanation")),
            comparison_label=payload.get("comparison_label", ""),
            summary=payload.get("summary", ""),
            booking_links=_optional_list_field(payload, "booking_links"),
            source_refs=_optional_list_field(payload, "source_refs"),
            tags=_optional_list_field(payload, "tags"),
            notes=_optional_list_field(payload, "notes"),
            schema_version=payload.get("schema_version", SCHEMA_VERSION),
        )
