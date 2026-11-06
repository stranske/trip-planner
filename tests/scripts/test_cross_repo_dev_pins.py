"""Dev-tool pins must co-resolve with the pinned Travel-Plan-Permission checkout.

The cross-repo smoke job installs ``TPP[dev]`` and ``trip-planner[dev]`` into one
interpreter. When a dev-tool sync bumps an exact pin here (for example
``ruff==0.17.2`` -> ``ruff==0.17.3``) while ``TPP_PINNED_REF`` still points at a
TPP revision carrying the old pin, pip fails with ``ResolutionImpossible``
(issue #1967). This test names the conflicting package and the fix up front.

It needs a TPP checkout: set ``TPP_REPO_PATH`` (the smoke workflow does) or
the test is skipped. Run with
``TPP_REPO_PATH=../Travel-Plan-Permission pytest tests/scripts/test_cross_repo_dev_pins.py``.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parents[2]


def _requirements(pyproject: Path) -> dict[str, list[Requirement]]:
    project = tomllib.loads(pyproject.read_text())["project"]
    entries = list(project.get("dependencies", []))
    entries += project.get("optional-dependencies", {}).get("dev", [])
    requirements: dict[str, list[Requirement]] = {}
    for req in map(Requirement, entries):
        if req.marker is not None and not req.marker.evaluate({"extra": "dev"}):
            continue
        name = canonicalize_name(req.name)
        if name not in requirements:
            requirements[name] = []
        requirements[name].append(req)
    return requirements


def _exact_pin(req: Requirement) -> str | None:
    specs = list(req.specifier)
    if len(specs) == 1 and specs[0].operator == "==":
        version = specs[0].version
        # Reject wildcard equality like ==0.17.*
        if "*" in version or "?" in version:
            return None
        return version
    return None


def find_pin_conflicts(planner_pyproject: Path, tpp_pyproject: Path) -> list[str]:
    """Return one message per package whose exact pin the other side rejects."""
    planner = _requirements(planner_pyproject)
    tpp = _requirements(tpp_pyproject)
    conflicts = []
    for name in sorted(planner.keys() & tpp.keys()):
        planner_reqs = planner[name]
        tpp_reqs = tpp[name]
        conflict_found = False
        # Check all planner exact pins against all TPP constraints
        for planner_req in planner_reqs:
            version = _exact_pin(planner_req)
            if version is not None:
                for tpp_req in tpp_reqs:
                    if not tpp_req.specifier.contains(version, prereleases=True):
                        conflicts.append(
                            f"{name}: trip-planner '{planner_req}' vs TPP '{tpp_req}'"
                        )
                        conflict_found = True
                        break
                if conflict_found:
                    break
        if conflict_found:
            continue
        # Check all TPP exact pins against all planner constraints
        for tpp_req in tpp_reqs:
            version = _exact_pin(tpp_req)
            if version is not None:
                for planner_req in planner_reqs:
                    if not planner_req.specifier.contains(version, prereleases=True):
                        conflicts.append(
                            f"{name}: trip-planner '{planner_req}' vs TPP '{tpp_req}'"
                        )
                        conflict_found = True
                        break
                if conflict_found:
                    break
    return conflicts


def test_find_pin_conflicts_flags_diverged_exact_pin(tmp_path: Path) -> None:
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\ndev = ["ruff==0.17.3", "numpy==2.5.1"]\n'
    )
    tpp.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\ndev = ["ruff==0.17.2", "numpy>=1.24.0"]\n'
    )

    assert find_pin_conflicts(planner, tpp) == [
        "ruff: trip-planner 'ruff==0.17.3' vs TPP 'ruff==0.17.2'"
    ]


def test_find_pin_conflicts_ignores_inactive_markers(tmp_path: Path) -> None:
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\ndev = ["ruff==0.17.3"]\n'
    )
    tpp.write_text(
        "[project]\ndependencies = []\n[project.optional-dependencies]\n"
        "dev = [\"ruff==0.17.2; python_version < '3.0'\"]\n"
    )

    assert find_pin_conflicts(planner, tpp) == []


def test_find_pin_conflicts_flags_active_marker_pin(tmp_path: Path) -> None:
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\ndev = ["ruff==0.17.3"]\n'
    )
    tpp.write_text(
        "[project]\ndependencies = []\n[project.optional-dependencies]\n"
        "dev = [\"ruff==0.17.2; python_version >= '3.0'\"]\n"
    )

    assert find_pin_conflicts(planner, tpp) == [
        "ruff: trip-planner 'ruff==0.17.3' vs TPP 'ruff==0.17.2; python_version >= \"3.0\"'"
    ]


def test_find_pin_conflicts_exact_pin_with_range_in_tpp(tmp_path: Path) -> None:
    """Exact pin in planner, range constraint in TPP - same package name."""
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff==0.17.3"]\n'
    )
    tpp.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff<0.18.0,>=0.17.0"]\n'
    )

    # 0.17.3 is within >=0.17.0,<0.18.0, so no conflict
    assert find_pin_conflicts(planner, tpp) == []


def test_find_pin_conflicts_exact_pin_with_incompatible_range_in_tpp(tmp_path: Path) -> None:
    """Exact pin in planner, incompatible range constraint in TPP - same package name."""
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff==0.18.0"]\n'
    )
    tpp.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff>=0.17.0,<0.18.0"]\n'
    )

    # 0.18.0 is NOT within >=0.17.0,<0.18.0, so conflict
    # Note: packaging normalizes specifier order to <0.18.0,>=0.17.0
    assert find_pin_conflicts(planner, tpp) == [
        "ruff: trip-planner 'ruff==0.18.0' vs TPP 'ruff<0.18.0,>=0.17.0'"
    ]


def test_find_pin_conflicts_exact_pin_in_tpp_with_range_in_planner(tmp_path: Path) -> None:
    """Exact pin in TPP, range constraint in planner - same package name."""
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff>=0.17.0"]\n'
    )
    tpp.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff==0.17.3"]\n'
    )

    # 0.17.3 is within >=0.17.0, so no conflict
    assert find_pin_conflicts(planner, tpp) == []


def test_find_pin_conflicts_exact_pin_in_tpp_with_incompatible_range_in_planner(
    tmp_path: Path,
) -> None:
    """Exact pin in TPP, incompatible range constraint in planner - same package name."""
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff<0.17.0"]\n'
    )
    tpp.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff==0.17.3"]\n'
    )

    # 0.17.3 is NOT within <0.17.0, so conflict
    assert find_pin_conflicts(planner, tpp) == [
        "ruff: trip-planner 'ruff<0.17.0' vs TPP 'ruff==0.17.3'"
    ]


def test_find_pin_conflicts_wildcard_equality_not_treated_as_exact_pin(tmp_path: Path) -> None:
    """Wildcard equality like ==0.17.* should NOT be treated as an exact pin."""
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff==0.17.*"]\n'
    )
    tpp.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff==0.17.2"]\n'
    )

    # ==0.17.* is not an exact pin, so no conflict detected
    assert find_pin_conflicts(planner, tpp) == []


def test_find_pin_conflicts_compatible_wildcard_constraint(tmp_path: Path) -> None:
    """Compatible wildcard constraint should not cause conflict."""
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff==0.17.3"]\n'
    )
    tpp.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff>=0.17.0"]\n'
    )

    # 0.17.3 satisfies >=0.17.0
    assert find_pin_conflicts(planner, tpp) == []


def test_find_pin_conflicts_incompatible_wildcard_constraint(tmp_path: Path) -> None:
    """Incompatible wildcard/prefix constraint should cause conflict."""
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff==0.18.0"]\n'
    )
    tpp.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff<0.18.0,>=0.17.0"]\n'
    )

    # 0.18.0 does NOT satisfy >=0.17.0,<0.18.0
    assert find_pin_conflicts(planner, tpp) == [
        "ruff: trip-planner 'ruff==0.18.0' vs TPP 'ruff<0.18.0,>=0.17.0'"
    ]


def test_find_pin_conflicts_multiple_requirements_same_package(tmp_path: Path) -> None:
    """Multiple requirements for same package - should preserve all and check all pairs."""
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    # Planner has both an exact pin and a range for the same package
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff==0.17.3", "ruff>=0.17.0"]\n'
    )
    tpp.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff<0.18.0,>=0.17.0"]\n'
    )

    # All constraints are compatible, no conflict
    assert find_pin_conflicts(planner, tpp) == []


def test_find_pin_conflicts_multiple_requirements_with_conflict(tmp_path: Path) -> None:
    """Multiple requirements for same package with one conflicting."""
    planner = tmp_path / "planner.toml"
    tpp = tmp_path / "tpp.toml"
    # Planner has both an exact pin and a range for the same package
    planner.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff==0.18.0", "ruff>=0.17.0"]\n'
    )
    tpp.write_text(
        '[project]\ndependencies = []\n[project.optional-dependencies]\n'
        'dev = ["ruff<0.18.0,>=0.17.0"]\n'
    )

    # ruff==0.18.0 conflicts with <0.18.0
    assert find_pin_conflicts(planner, tpp) == [
        "ruff: trip-planner 'ruff==0.18.0' vs TPP 'ruff<0.18.0,>=0.17.0'"
    ]


def test_planner_dev_pins_resolve_with_pinned_tpp_checkout() -> None:
    tpp_repo = os.environ.get("TPP_REPO_PATH")
    if not tpp_repo:
        pytest.skip("TPP_REPO_PATH not set; the cross-repo smoke workflow provides it")
    tpp_pyproject = (REPO_ROOT / tpp_repo / "pyproject.toml").resolve()
    assert tpp_pyproject.is_file(), f"TPP checkout has no pyproject.toml at {tpp_pyproject}"

    conflicts = find_pin_conflicts(REPO_ROOT / "pyproject.toml", tpp_pyproject)

    assert not conflicts, (
        "trip-planner and the pinned TPP revision cannot be installed together:\n  "
        + "\n  ".join(conflicts)
        + "\nMove TPP_PINNED_REF in .github/workflows/cross-repo-smoke.yml to a TPP "
        "revision with matching pins, in the same PR as the pin update."
    )
