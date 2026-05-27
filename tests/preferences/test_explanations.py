from dataclasses import dataclass

from trip_planner.preferences.explanations import (
    DimensionResolutionExplanation,
    HybridFactorExplanation,
    InteractionActivation,
    MaterialInfluence,
    ResolutionExplanation,
    ResolvedLeisureProfile,
)


def test_material_influence_to_dict_round_trip() -> None:
    influence = MaterialInfluence(
        source_kind="evidence",
        source_id="ev-001",
        weight=0.8,
        summary="Traveler prefers rail travel",
    )

    assert influence.to_dict() == {
        "source_kind": "evidence",
        "source_id": "ev-001",
        "weight": 0.8,
        "summary": "Traveler prefers rail travel",
    }


def test_dimension_resolution_explanation_to_dict_with_influences() -> None:
    influence = MaterialInfluence(
        source_kind="evidence",
        source_id="ev-scenic-rail",
        weight=0.72,
        summary="Scenic rail segments are preferred over short-haul flights.",
    )
    explanation = DimensionResolutionExplanation(
        dimension_key="movement_vs_friction",
        initial_value=0.2,
        resolved_value=0.65,
        confidence=0.8,
        salience=0.7,
        stability=0.6,
        value_delta=0.45,
        influences=[influence],
        interaction_rule_ids=["rail-comfort-rule"],
        tension_flag_ids=["transfer-fatigue-conflict"],
        notes=["Explicit rail preference outweighed transfer friction."],
        explanation_code="explicit_override",
        explanation_text="Rail preference pushed the movement score higher.",
        contributing_evidence_ids=["ev-scenic-rail"],
    )

    assert explanation.to_dict() == {
        "dimension_key": "movement_vs_friction",
        "initial_value": 0.2,
        "resolved_value": 0.65,
        "confidence": 0.8,
        "salience": 0.7,
        "stability": 0.6,
        "value_delta": 0.45,
        "influences": [influence.to_dict()],
        "interaction_rule_ids": ["rail-comfort-rule"],
        "tension_flag_ids": ["transfer-fatigue-conflict"],
        "notes": ["Explicit rail preference outweighed transfer friction."],
        "explanation_code": "explicit_override",
        "explanation_text": "Rail preference pushed the movement score higher.",
        "contributing_evidence_ids": ["ev-scenic-rail"],
    }


def test_resolution_explanation_empty_and_populated() -> None:
    assert ResolutionExplanation().to_dict() == {
        "dimension_explanations": {},
        "hybrid_factor_explanations": {},
        "activated_interactions": [],
        "tension_explanations": {},
    }

    dimension = DimensionResolutionExplanation(
        dimension_key="iconic_vs_discovery",
        initial_value=0.0,
        resolved_value=-0.4,
        confidence=0.55,
        salience=0.7,
        stability=0.5,
    )
    hybrid = HybridFactorExplanation(
        hybrid_factor_key="local_texture",
        mode="weighted",
        salience=0.6,
        anchor_strength=0.3,
        influences=[
            MaterialInfluence(
                source_kind="anchor",
                source_id="anchor-local-markets",
                weight=0.3,
                summary="Local market anchor informs discovery weighting.",
            )
        ],
    )
    interaction = InteractionActivation(
        rule_id="discovery-depth-bias",
        dimensions=["iconic_vs_discovery"],
        planning_biases={"neighborhood_depth": 0.4},
        triggered_tension_ids=["breadth-recovery-conflict"],
        notes=["Bias activated for slower local exploration."],
    )
    tension_influence = MaterialInfluence(
        source_kind="tension",
        source_id="breadth-recovery-conflict",
        weight=0.4,
        summary="Breadth is capped by recovery needs.",
    )

    populated = ResolutionExplanation(
        dimension_explanations={"iconic_vs_discovery": dimension},
        hybrid_factor_explanations={"local_texture": hybrid},
        activated_interactions=[interaction],
        tension_explanations={"breadth-recovery-conflict": [tension_influence]},
    ).to_dict()

    assert populated == {
        "dimension_explanations": {"iconic_vs_discovery": dimension.to_dict()},
        "hybrid_factor_explanations": {"local_texture": hybrid.to_dict()},
        "activated_interactions": [interaction.to_dict()],
        "tension_explanations": {
            "breadth-recovery-conflict": [tension_influence.to_dict()],
        },
    }


def test_explanation_code_default_is_default_seed() -> None:
    explanation = DimensionResolutionExplanation(
        dimension_key="recovery_vs_intensity",
        initial_value=0.1,
        resolved_value=0.1,
        confidence=0.2,
        salience=0.3,
        stability=0.4,
    )

    assert explanation.explanation_code == "default_seed"


def test_resolved_leisure_profile_to_dict_delegates_profile_and_explanation() -> None:
    @dataclass
    class ProfileStub:
        profile_id: str

        def to_dict(self) -> dict[str, str]:
            return {"profile_id": self.profile_id}

    explanation = ResolutionExplanation(
        dimension_explanations={
            "movement_vs_friction": DimensionResolutionExplanation(
                dimension_key="movement_vs_friction",
                initial_value=0.2,
                resolved_value=0.5,
                confidence=0.7,
                salience=0.6,
                stability=0.5,
            )
        }
    )
    resolved = ResolvedLeisureProfile(
        profile=ProfileStub(profile_id="profile-scenic-rail"),
        explanation=explanation,
    )

    assert resolved.to_dict() == {
        "profile": {"profile_id": "profile-scenic-rail"},
        "explanation": explanation.to_dict(),
    }
