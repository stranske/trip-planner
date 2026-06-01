import pytest

import trip_planner.preferences.fixture_corpus as fixture_corpus
from trip_planner.preferences.fixture_corpus import (
    _build_fixture,
    build_evidence_record,
    build_profile_from_overrides,
    load_fixture_corpus,
    load_fixture_map,
)


def _fixture_payload() -> dict:
    return {
        "id": "fixture-rich",
        "fixture_kind": "archetype",
        "summary": "A traveler balancing rail movement and rest.",
        "tags": ["rail", "rest"],
        "raw_inputs": {
            "trip_brief": "Build a rail-first trip.",
            "stated_constraints": ["avoid tight transfers"],
        },
        "intended_interpretation": {
            "qualitative_summary": "Rail is preferred, but recovery remains important.",
            "dominant_dimensions": ["movement_vs_friction"],
            "expected_tensions": ["pace"],
            "planning_implications": ["prefer longer stops"],
        },
        "profile_overrides": {
            "trip_frame": {
                "duration_days": 21,
                "traveler_party": "pair",
                "season_window": ["spring"],
                "regions_in_scope": ["Japan"],
            },
            "hard_constraints": {
                "date_window": {"start": "2026-04-01", "end": "2026-04-21"},
                "duration_bounds": {"min_days": 18, "max_days": 24},
                "budget_ceiling": 9000,
                "must_include_places": ["Kyoto"],
                "mobility_constraints": ["rail preferred"],
            },
            "budget_model": {
                "total_budget_sensitivity": 0.65,
                "spending_priorities": {"lodging": 0.7},
                "quality_floors": {"transport": "rail"},
                "splurge_allowed": True,
                "splurge_style": "one ryokan",
            },
            "anchors": {
                "place_anchors": [
                    {
                        "type": "city",
                        "label": "Kyoto",
                        "strength": 0.9,
                        "flexibility": 0.2,
                        "notes": "Must include.",
                    }
                ]
            },
            "tradeoff_dimensions": {
                "movement_vs_friction": {
                    "value": -0.4,
                    "confidence": 0.8,
                    "salience": 0.7,
                    "stability": 0.6,
                    "scope": "global",
                    "notes": "Rail is okay, rushed transfers are not.",
                }
            },
            "hybrid_factors": {
                "rest": {
                    "mode": "anchor",
                    "salience": 0.8,
                    "anchor_strength": 0.75,
                    "tradeoff_role": "rhythm",
                    "preferences": {"late_start": 0.6},
                }
            },
            "interaction_rules": [
                {
                    "id": "rail-rest",
                    "dimensions": ["movement_vs_friction", "recovery_vs_intensity"],
                    "activation": {"when": "many transfers"},
                    "effect": {"prefer": "longer stays"},
                    "strength": 0.7,
                    "priority": 0.6,
                }
            ],
            "tension_flags": [
                {
                    "id": "pace-tension",
                    "severity": 0.5,
                    "description": "Rail ambition can crowd recovery.",
                }
            ],
            "conditional_overrides": [{"when": "rain", "prefer": "indoor alternates"}],
            "evidence_summary": {
                "sources": {"questionnaire": ["rail", "rest"]},
                "confidence_notes": ["direct traveler statements"],
            },
        },
        "evidence": [
            {
                "id": "ev-rail",
                "evidence_type": "option_selection",
                "source_type": "option_menu",
                "affected_dimensions": ["movement_vs_friction"],
                "affected_hybrid_factors": ["rest"],
                "anchor_groups": ["place_anchors"],
                "sequence": 1,
                "note": "Selected rail bundle.",
                "option_evidence": {
                    "option_set_id": "set-1",
                    "option_id": "rail-loop",
                    "option_kind": "mixed_bundle",
                    "presented_option_ids": ["rail-loop", "flight-hop"],
                    "comparison_label": "rail vs flight",
                },
                "contradictions": [
                    {
                        "previous_evidence_id": "ev-fast",
                        "reason": "Later choice prioritized recovery.",
                        "weakening_strength": 0.4,
                    }
                ],
            }
        ],
    }


def test_packaged_fixture_corpus_loads_from_runtime_resource() -> None:
    fixtures = load_fixture_corpus()

    assert fixtures
    assert "urban-historian" in {fixture.id for fixture in fixtures}
    fixture = load_fixture_map()["urban-historian"]
    assert fixture.profile.to_dict()["profile_kind"] == "leisure"
    assert fixture.intended_interpretation.qualitative_summary


def test_packaged_fixture_corpus_validates_resource_payload(monkeypatch) -> None:
    class FakeResource:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def joinpath(self, _name: str) -> "FakeResource":
            return self

        def read_text(self, *, encoding: str) -> str:
            assert encoding == "utf-8"
            return __import__("json").dumps(self.payload)

    def patch_payload(payload: dict) -> None:
        monkeypatch.setattr(
            fixture_corpus.resources,
            "files",
            lambda _package: FakeResource(payload),
        )

    patch_payload({"schema_version": "bad", "fixtures": []})
    with pytest.raises(ValueError, match="schema_version"):
        load_fixture_corpus()

    patch_payload({"schema_version": fixture_corpus.SCHEMA_VERSION, "fixtures": "bad"})
    with pytest.raises(ValueError, match="fixtures must be a list"):
        load_fixture_corpus()

    duplicate = _fixture_payload()
    patch_payload(
        {
            "schema_version": fixture_corpus.SCHEMA_VERSION,
            "fixtures": [duplicate, duplicate],
        }
    )
    with pytest.raises(ValueError, match="ids must be unique"):
        load_fixture_corpus()


def test_build_fixture_applies_nested_profile_and_evidence_overrides() -> None:
    fixture = _build_fixture(0, _fixture_payload())

    assert fixture.id == "fixture-rich"
    assert fixture.raw_inputs["trip_brief"] == "Build a rail-first trip."
    assert fixture.profile.trip_frame.duration_days == 21
    assert fixture.profile.hard_constraints.date_window.start == "2026-04-01"
    assert fixture.profile.hard_constraints.duration_bounds.max_days == 24
    assert fixture.profile.hard_constraints.must_include_places == ["Kyoto"]
    assert fixture.profile.budget_model.splurge_allowed is True
    assert fixture.profile.anchors["place_anchors"][0].label == "Kyoto"
    assert fixture.profile.tradeoff_dimensions["movement_vs_friction"].value == -0.4
    assert fixture.profile.hybrid_factors["rest"].tradeoff_role == "rhythm"
    assert fixture.profile.interaction_rules[0].id == "rail-rest"
    assert fixture.profile.tension_flags[0].id == "pace-tension"
    assert fixture.profile.conditional_overrides == [{"when": "rain", "prefer": "indoor alternates"}]
    assert fixture.profile.evidence_summary.sources["questionnaire"] == ["rail", "rest"]
    assert fixture.evidence[0].option_evidence is not None
    assert fixture.evidence[0].option_evidence.option_id == "rail-loop"
    assert fixture.evidence[0].contradictions[0].previous_evidence_id == "ev-fast"


def test_build_evidence_record_uses_baseline_defaults_without_optional_payloads() -> None:
    record = build_evidence_record(
        {
            "id": "ev-defaults",
            "evidence_type": "direct_statement",
            "source_type": "structured_input",
            "affected_dimensions": ["movement_vs_friction"],
            "sequence": 0,
        }
    )

    assert record.signal_direction == "positive"
    assert record.confidence_hint > 0
    assert record.salience_hint == 0.5
    assert record.option_evidence is None
    assert record.contradictions == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"hard_constraints": {"unknown": True}}, "hard constraint override keys"),
        ({"hard_constraints": {"date_window": {"timezone": "UTC"}}}, "date_window"),
        ({"hard_constraints": {"duration_bounds": {"ideal_days": 20}}}, "duration_bounds"),
        ({"tradeoff_dimensions": {"unknown": {"value": 0.1}}}, "tradeoff dimension"),
        ({"hybrid_factors": {"unknown": {"mode": "anchor"}}}, "hybrid factor"),
        ({"anchors": {"unknown": []}}, "anchor group"),
    ],
)
def test_profile_override_validation_rejects_unknown_keys(
    overrides: dict, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_profile_from_overrides(overrides)


@pytest.mark.parametrize(
    ("payload_update", "message"),
    [
        (lambda payload: payload.update({"id": ""}), "must define id"),
        (
            lambda payload: payload.update({"intended_interpretation": "summary"}),
            "intended_interpretation",
        ),
        (lambda payload: payload.update({"raw_inputs": "brief"}), "raw_inputs"),
        (
            lambda payload: payload["intended_interpretation"].update(
                {"qualitative_summary": ""}
            ),
            "qualitative_summary",
        ),
    ],
)
def test_build_fixture_validation_rejects_malformed_payloads(
    payload_update, message: str
) -> None:
    payload = _fixture_payload()
    payload_update(payload)

    with pytest.raises(ValueError, match=message):
        _build_fixture(0, payload)


def test_build_fixture_validation_rejects_non_object_entries() -> None:
    with pytest.raises(ValueError, match="index 3"):
        _build_fixture(3, "not-a-fixture")
