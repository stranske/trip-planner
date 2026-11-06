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


def _requirements(pyproject: Path) -> dict[str, Requirement]:
    project = tomllib.loads(pyproject.read_text())["project"]
    entries = list(project.get("dependencies", []))
    entries += project.get("optional-dependencies", {}).get("dev", [])
    requirements: dict[str, Requirement] = {}
    for req in map(Requirement, entries):
        if req.marker is not None and not req.marker.evaluate({"extra": "dev"}):
            continue
        requirements[canonicalize_name(req.name)] = req
    return requirements


def _exact_pin(req: Requirement) -> str | None:
    specs = list(req.specifier)
    if len(specs) == 1 and specs[0].operator == "==":
        return specs[0].version
    return None


def find_pin_conflicts(planner_pyproject: Path, tpp_pyproject: Path) -> list[str]:
    """Return one message per package whose exact pin the other side rejects."""
    planner = _requirements(planner_pyproject)
    tpp = _requirements(tpp_pyproject)
    conflicts = []
    for name in sorted(planner.keys() & tpp.keys()):
        for pinned, other in ((planner[name], tpp[name]), (tpp[name], planner[name])):
            version = _exact_pin(pinned)
            if version is not None and not other.specifier.contains(version, prereleases=True):
                conflicts.append(f"{name}: trip-planner '{planner[name]}' vs TPP '{tpp[name]}'")
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
