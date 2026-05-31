"""Baseline scenarios for preference resolution (``resolve_dimension_evidence``).

Issue #1268 acceptance criteria require at least one preference-resolution
baseline scenario with directional and/or invariant checks.
``resolve_dimension_evidence`` is deterministic given a dimension key, a seed
value, and a list of evidence records (no DB, network, or LLM), so its resolved
value / confidence is a stable baseline surface.

Inputs are drawn from the existing deterministic leisure-traveler fixture
corpus; checks use the shared ``baseline_kit`` directional/invariant primitives.
"""

from __future__ import annotations

import math

import pytest
from baseline_kit import InvariantResult, assert_invariants, evaluate_direction

from tests.preferences.fixture_corpus import load_fixture_corpus
from trip_planner.preferences.resolution import resolve_dimension_evidence

_CORPUS = {f.id: f for f in load_fixture_corpus()}

# A dimension key no fixture's evidence affects -> the resolver retains the seed
# value at zero confidence. Used as the "no signal" control for directional checks.
_NO_EVIDENCE_DIM = "__no_such_dimension__"

# Fixtures whose dominant dimensions carry strong explicit/behavioral evidence.
_SCENARIO_IDS = [
    "scenic-rail-nomad",
    "urban-historian",
    "discovery-wanderer",
    "food-splurger",
]


def _resolve_dominant(fixture):
    dimension_key = fixture.intended_interpretation.dominant_dimensions[0]
    seed = fixture.profile.tradeoff_dimensions[dimension_key].value
    resolved = resolve_dimension_evidence(dimension_key, seed, fixture.evidence)
    return dimension_key, seed, resolved


@pytest.mark.parametrize("fid", _SCENARIO_IDS)
def test_evidence_raises_confidence_over_no_evidence(fid):
    """Directional: a dominant dimension backed by applicable evidence resolves
    with higher confidence than a dimension with no applicable evidence."""
    fixture = _CORPUS[fid]
    _, _, resolved = _resolve_dominant(fixture)
    no_evidence = resolve_dimension_evidence(_NO_EVIDENCE_DIM, 0.4, fixture.evidence)
    assert evaluate_direction(
        "greater_than", resolved.confidence, no_evidence.confidence
    ), (
        f"{fid}: evidence-backed confidence {resolved.confidence:.4f} should exceed "
        f"no-evidence confidence {no_evidence.confidence:.4f}"
    )


@pytest.mark.parametrize("fid", _SCENARIO_IDS)
def test_resolution_invariants(fid):
    fixture = _CORPUS[fid]
    dimension_key, seed, r = _resolve_dominant(fixture)
    evidence_ids = {e.id for e in fixture.evidence}
    results = [
        InvariantResult(
            f"{fid}_final_value_in_axis",
            -1.0 <= r.final_value <= 1.0,
            detail=f"final_value={r.final_value}",
        ),
        InvariantResult(
            f"{fid}_confidence_unit_interval",
            0.0 <= r.confidence <= 1.0,
            detail=f"confidence={r.confidence}",
        ),
        InvariantResult(
            f"{fid}_behavior_support_finite",
            math.isfinite(r.recent_behavior_support)
            and math.isfinite(r.older_behavior_support),
            detail=f"recent={r.recent_behavior_support} older={r.older_behavior_support}",
        ),
        InvariantResult(
            f"{fid}_contrib_ids_subset",
            set(r.contributing_evidence_ids) <= evidence_ids,
            detail=str(r.contributing_evidence_ids),
        ),
        InvariantResult(
            f"{fid}_contrib_ids_bounded",
            len(r.contributing_evidence_ids) <= 5,
            detail=str(len(r.contributing_evidence_ids)),
        ),
    ]
    # Resolution is deterministic for the same inputs.
    again = resolve_dimension_evidence(dimension_key, seed, fixture.evidence)
    results.append(
        InvariantResult(
            f"{fid}_deterministic",
            (again.final_value, again.confidence, again.explanation_code)
            == (r.final_value, r.confidence, r.explanation_code),
            detail="non-deterministic resolution",
        )
    )
    assert_invariants(results, context=f"preference_resolution_baseline[{fid}]")


def test_no_evidence_retains_seed_at_zero_confidence():
    """Invariant: with no applicable evidence the resolver returns the seed value
    unchanged, at zero confidence, with the ``default_seed`` explanation code."""
    fixture = _CORPUS["scenic-rail-nomad"]
    seed = 0.37
    r = resolve_dimension_evidence(_NO_EVIDENCE_DIM, seed, fixture.evidence)
    results = [
        InvariantResult(
            "no_evidence_retains_seed",
            r.final_value == seed,
            detail=f"final={r.final_value} seed={seed}",
        ),
        InvariantResult(
            "no_evidence_zero_confidence",
            r.confidence == 0.0,
            detail=f"confidence={r.confidence}",
        ),
        InvariantResult(
            "no_evidence_default_code",
            r.explanation_code == "default_seed",
            detail=r.explanation_code,
        ),
    ]
    assert_invariants(results, context="preference_resolution_no_evidence")
