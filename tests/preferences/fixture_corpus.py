from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trip_planner.preferences.evidence import (
    ContradictionMarker,
    OptionEvidence,
    PreferenceEvidence,
)
from trip_planner.preferences.models import (
    Anchor,
    BudgetModel,
    DateWindow,
    DurationBounds,
    EvidenceSummary,
    HardConstraints,
    HybridFactor,
    InteractionRule,
    LeisurePreferenceProfile,
    TensionFlag,
    TradeoffDimension,
    TripFrame,
)
from trip_planner.preferences.schema import (
    ANCHOR_GROUPS,
    HYBRID_FACTOR_KEYS,
    SCHEMA_VERSION,
    TRADEOFF_DIMENSION_KEYS,
)


@dataclass(slots=True)
class IntendedInterpretation:
    qualitative_summary: str
    dominant_dimensions: list[str]
    expected_tensions: list[str]
    planning_implications: list[str]


@dataclass(slots=True)
class TravelerFixture:
    id: str
    fixture_kind: str
    summary: str
    tags: list[str]
    raw_inputs: dict[str, Any]
    intended_interpretation: IntendedInterpretation
    profile: LeisurePreferenceProfile
    evidence: list[PreferenceEvidence]


def fixture_corpus_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "preferences"
        / "leisure_traveler_corpus.json"
    )


def load_fixture_corpus(path: Path | None = None) -> list[TravelerFixture]:
    payload = json.loads((path or fixture_corpus_path()).read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "fixture corpus schema_version must match trip_planner.preferences.schema.SCHEMA_VERSION"
        )
    fixtures = payload.get("fixtures", [])
    if not isinstance(fixtures, list):
        raise ValueError("fixtures must be a list")
    fixture_objects = [_build_fixture(entry) for entry in fixtures]
    fixture_ids = [fixture.id for fixture in fixture_objects]
    if len(set(fixture_ids)) != len(fixture_ids):
        raise ValueError("fixture corpus ids must be unique")
    return fixture_objects


def load_fixture_map() -> dict[str, TravelerFixture]:
    return {fixture.id: fixture for fixture in load_fixture_corpus()}


def _build_fixture(payload: dict[str, Any]) -> TravelerFixture:
    intended = payload.get("intended_interpretation", {})
    profile = build_profile_from_overrides(payload.get("profile_overrides", {}))
    evidence = [build_evidence_record(item) for item in payload.get("evidence", [])]
    if not intended.get("qualitative_summary"):
        raise ValueError(
            f"fixture {payload.get('id', '<unknown>')!r} must define intended_interpretation."
            "qualitative_summary"
        )
    return TravelerFixture(
        id=payload["id"],
        fixture_kind=payload["fixture_kind"],
        summary=payload["summary"],
        tags=list(payload.get("tags", [])),
        raw_inputs=dict(payload.get("raw_inputs", {})),
        intended_interpretation=IntendedInterpretation(
            qualitative_summary=intended["qualitative_summary"],
            dominant_dimensions=list(intended.get("dominant_dimensions", [])),
            expected_tensions=list(intended.get("expected_tensions", [])),
            planning_implications=list(intended.get("planning_implications", [])),
        ),
        profile=profile,
        evidence=evidence,
    )


def build_profile_from_overrides(overrides: dict[str, Any]) -> LeisurePreferenceProfile:
    profile_payload = _default_profile_payload()

    trip_frame_overrides = overrides.get("trip_frame", {})
    profile_payload["trip_frame"] = {**profile_payload["trip_frame"], **trip_frame_overrides}

    hard_constraint_overrides = overrides.get("hard_constraints", {})
    date_window = {
        **profile_payload["hard_constraints"]["date_window"],
        **hard_constraint_overrides.get("date_window", {}),
    }
    duration_bounds = {
        **profile_payload["hard_constraints"]["duration_bounds"],
        **hard_constraint_overrides.get("duration_bounds", {}),
    }
    merged_constraints = {
        **profile_payload["hard_constraints"],
        **hard_constraint_overrides,
        "date_window": date_window,
        "duration_bounds": duration_bounds,
    }
    profile_payload["hard_constraints"] = merged_constraints

    budget_overrides = overrides.get("budget_model", {})
    profile_payload["budget_model"] = {**profile_payload["budget_model"], **budget_overrides}

    for key, values in overrides.get("tradeoff_dimensions", {}).items():
        if key not in profile_payload["tradeoff_dimensions"]:
            raise ValueError(f"unsupported tradeoff dimension override: {key}")
        profile_payload["tradeoff_dimensions"][key] = {
            **profile_payload["tradeoff_dimensions"][key],
            **values,
        }

    for key, values in overrides.get("hybrid_factors", {}).items():
        if key not in profile_payload["hybrid_factors"]:
            raise ValueError(f"unsupported hybrid factor override: {key}")
        profile_payload["hybrid_factors"][key] = {
            **profile_payload["hybrid_factors"][key],
            **values,
        }

    anchor_overrides = overrides.get("anchors", {})
    for group, values in anchor_overrides.items():
        if group not in profile_payload["anchors"]:
            raise ValueError(f"unsupported anchor group override: {group}")
        profile_payload["anchors"][group] = list(values)

    for key in ("interaction_rules", "tension_flags", "conditional_overrides"):
        if key in overrides:
            profile_payload[key] = deepcopy(overrides[key])
    if "evidence_summary" in overrides:
        profile_payload["evidence_summary"] = {
            **profile_payload["evidence_summary"],
            **overrides["evidence_summary"],
        }

    return LeisurePreferenceProfile(
        trip_frame=TripFrame(**profile_payload["trip_frame"]),
        hard_constraints=HardConstraints(
            date_window=DateWindow(**profile_payload["hard_constraints"]["date_window"]),
            duration_bounds=DurationBounds(
                **profile_payload["hard_constraints"]["duration_bounds"]
            ),
            budget_ceiling=profile_payload["hard_constraints"].get("budget_ceiling"),
            must_include_places=list(
                profile_payload["hard_constraints"].get("must_include_places", [])
            ),
            must_protect_experiences=list(
                profile_payload["hard_constraints"].get("must_protect_experiences", [])
            ),
            mobility_constraints=list(
                profile_payload["hard_constraints"].get("mobility_constraints", [])
            ),
            lodging_constraints=list(
                profile_payload["hard_constraints"].get("lodging_constraints", [])
            ),
            visa_border_constraints=list(
                profile_payload["hard_constraints"].get("visa_border_constraints", [])
            ),
        ),
        anchors={
            group: [Anchor(**anchor) for anchor in anchors]
            for group, anchors in profile_payload["anchors"].items()
        },
        budget_model=BudgetModel(**profile_payload["budget_model"]),
        tradeoff_dimensions={
            key: TradeoffDimension(**values)
            for key, values in profile_payload["tradeoff_dimensions"].items()
        },
        hybrid_factors={
            key: HybridFactor(**values) for key, values in profile_payload["hybrid_factors"].items()
        },
        conditional_overrides=list(profile_payload["conditional_overrides"]),
        interaction_rules=[
            InteractionRule(**rule) for rule in profile_payload["interaction_rules"]
        ],
        tension_flags=[TensionFlag(**flag) for flag in profile_payload["tension_flags"]],
        evidence_summary=EvidenceSummary(**profile_payload["evidence_summary"]),
    )


def build_evidence_record(payload: dict[str, Any]) -> PreferenceEvidence:
    option_evidence = payload.get("option_evidence")
    contradictions = payload.get("contradictions", [])
    return PreferenceEvidence(
        id=payload["id"],
        evidence_type=payload["evidence_type"],
        source_type=payload["source_type"],
        affected_dimensions=list(payload.get("affected_dimensions", [])),
        affected_hybrid_factors=list(payload.get("affected_hybrid_factors", [])),
        anchor_groups=list(payload.get("anchor_groups", [])),
        signal_direction=payload.get("signal_direction", "positive"),
        confidence_hint=payload.get("confidence_hint", 0.5),
        salience_hint=payload.get("salience_hint", 0.5),
        observed_at=payload.get("observed_at"),
        sequence=payload.get("sequence"),
        note=payload.get("note", ""),
        option_evidence=OptionEvidence(**option_evidence) if option_evidence else None,
        contradictions=[ContradictionMarker(**item) for item in contradictions],
    )


def _default_profile_payload() -> dict[str, Any]:
    return {
        "trip_frame": {
            "duration_days": 28,
            "traveler_party": "solo",
            "season_window": [],
            "trip_stage": "mixed",
            "regions_in_scope": [],
            "special_themes": [],
        },
        "hard_constraints": {
            "date_window": {"start": None, "end": None},
            "duration_bounds": {"min_days": 14, "max_days": 42},
            "budget_ceiling": None,
            "must_include_places": [],
            "must_protect_experiences": [],
            "mobility_constraints": [],
            "lodging_constraints": [],
            "visa_border_constraints": [],
        },
        "budget_model": {
            "total_budget_sensitivity": 0.5,
            "spending_priorities": {},
            "quality_floors": {},
            "splurge_allowed": False,
            "splurge_style": None,
        },
        "anchors": {group: [] for group in ANCHOR_GROUPS},
        "tradeoff_dimensions": {
            key: {
                "value": 0.0,
                "confidence": 0.4,
                "salience": 0.4,
                "stability": 0.4,
                "trip_stage_sensitivity": {
                    "initial_design": 0.3,
                    "inventory_selection": 0.3,
                    "daily_activity_design": 0.3,
                    "in_trip_adjustment": 0.3,
                },
                "scope": "global",
                "notes": "",
            }
            for key in TRADEOFF_DIMENSION_KEYS
        },
        "hybrid_factors": {
            key: {
                "mode": "tradeoff",
                "salience": 0.2,
                "anchor_strength": 0.0,
                "tradeoff_role": "none",
                "notes": "",
                "preferences": {},
            }
            for key in HYBRID_FACTOR_KEYS
        },
        "conditional_overrides": [],
        "interaction_rules": [],
        "tension_flags": [],
        "evidence_summary": {"sources": {}, "confidence_notes": []},
    }
