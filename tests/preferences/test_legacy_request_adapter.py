import json
from pathlib import Path

from trip_planner.preferences.legacy_request_adapter import (
    adapt_legacy_request,
    load_legacy_request,
)


def test_legacy_request_adapter_maps_existing_request_shape() -> None:
    request_path = Path("request.json")
    payload = json.loads(request_path.read_text(encoding="utf-8"))

    profile = adapt_legacy_request(payload)

    assert profile.hard_constraints.must_include_places == payload["must_see"]
    assert profile.trip_frame.season_window == payload["trip_window"]["months"]
    assert profile.budget_model.total_budget_sensitivity == payload["cost_sensitivity"]
    assert (
        "Mapped from legacy nature_ratio field."
        in profile.tradeoff_dimensions["nature_vs_culture"].notes
    )
    assert profile.hybrid_factors["route_modes"].preferences["rail"] == 1.0


def test_legacy_request_adapter_maps_nature_ratio_onto_canonical_axis() -> None:
    profile = adapt_legacy_request(
        {
            "trip_window": {"months": ["May"]},
            "must_see": [],
            "nature_ratio": 0.75,
            "complexity_tolerance": "medium",
            "cost_sensitivity": 0.3,
        }
    )

    assert profile.tradeoff_dimensions["nature_vs_culture"].value == 0.5


def test_legacy_request_adapter_maps_complexity_tolerance() -> None:
    profile = adapt_legacy_request(
        {
            "trip_window": {"months": ["June"]},
            "must_see": [],
            "nature_ratio": 0.5,
            "complexity_tolerance": "low",
            "cost_sensitivity": 0.3,
        }
    )

    assert profile.tradeoff_dimensions["movement_vs_friction"].value < 0
    assert profile.tradeoff_dimensions["recovery_vs_intensity"].value > 0
    assert profile.tradeoff_dimensions["self_reliance_vs_convenience"].value < 0


def test_legacy_request_adapter_rejects_invalid_budget_sensitivity() -> None:
    try:
        adapt_legacy_request(
            {
                "trip_window": {"months": ["June"]},
                "must_see": [],
                "nature_ratio": 0.5,
                "complexity_tolerance": "medium",
                "cost_sensitivity": 1.5,
            }
        )
    except ValueError as exc:
        assert "total_budget_sensitivity" in str(exc)
    else:
        raise AssertionError("Invalid legacy budget sensitivity should fail validation")


def test_load_legacy_request_reads_from_path(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "trip_window": {
                    "months": ["September"],
                    "min_weeks": 2,
                    "max_weeks": 3,
                },
                "must_see": ["Kyoto"],
                "nature_ratio": 0.4,
                "complexity_tolerance": "high",
                "cost_sensitivity": 0.2,
                "route_passions": {"train": 4},
            }
        ),
        encoding="utf-8",
    )

    profile = load_legacy_request(request_path)

    assert profile.hard_constraints.must_include_places == ["Kyoto"]
    assert profile.hybrid_factors["route_modes"].preferences["rail"] == 1.0


def _coverage_map_reference_errors(text: str, root: Path) -> list[str]:
    """Validate explicit citations, not implementation or test behavior."""
    import re

    errors = []
    for token in re.findall(r"(?<!`)`([^`\n]+)`(?!`)", text):
        if any(character.isspace() for character in token):
            continue
        is_path = (
            token.endswith("/")
            or token == "Makefile"
            or re.search(r"\.(?:py|tsx?|ya?ml|md)$", token)
        )
        if not is_path:
            continue
        candidate = root / token
        if not candidate.exists():
            errors.append(f"Missing explicit path: {token}")
        elif not candidate.resolve().is_relative_to(root.resolve()):
            errors.append(f"Path escapes repository: {token}")
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        if "://" in target or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        if not path:
            continue
        candidate = root / "docs" / path
        if not candidate.exists() or not candidate.resolve().is_relative_to(root.resolve()):
            errors.append(f"Missing document-relative link: {target}")
    return errors


def test_design_coverage_map_references_are_addressable() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/design-coverage-map.md").read_text()
    assert _coverage_map_reference_errors(text, root) == []


def test_coverage_map_path_check_rejects_missing_and_accepts_same_directory_links() -> None:
    root = Path(__file__).resolve().parents[2]
    assert _coverage_map_reference_errors("`tests/no-such-coverage-proof.py`", root)
    assert _coverage_map_reference_errors("[contract](domain-contracts.md)", root) == []


def test_coverage_map_keeps_claims_scoped_to_their_evidence() -> None:
    import re

    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/design-coverage-map.md").read_text()
    normalized = " ".join(text.split())
    legacy = next(
        line for line in text.splitlines() if line.startswith("| Legacy request adapter |")
    )
    assert "tests/preferences/test_legacy_request_adapter.py" in legacy
    assert "no dedicated test" not in legacy
    assert "allow_fixture_fallback=False" in text
    assert "Current configured execution: UNVERIFIED" in text
    assert "Path validity is a documentation check, not behavioral verification" in normalized
    assert "Historical May baseline (not rerun)" in text
    assert "976 passed, 1 xfailed" in text
    for owner in ("F50", "F51", "F52"):
        assert owner in text
    workflow = (root / ".github/workflows/cross-repo-smoke.yml").read_text()
    pin = re.search(r"TPP_PINNED_REF: ([0-9a-f]{40})", workflow)
    assert pin is not None and pin.group(1) in text
    assert "tests/integration/test_authenticated_two_app_handoff.py" in text
    assert "python scripts/check_full_product_verification.py --live-tpp=required" in text
    partial_rows = [
        line for line in text.splitlines() if line.startswith("|") and "🟡 Partial" in line
    ]
    for row in partial_rows:
        if row.startswith("| 🟡 Partial |"):
            continue  # Legend, not a delivery claim.
        assert "UNVERIFIED" in row and "Required gate" in row
