"""Dev-tool pins must co-resolve with the pinned Travel-Plan-Permission checkout.

The cross-repo smoke job installs ``TPP[dev]`` and ``trip-planner[dev]`` into one
interpreter. When a dev-tool sync bumps an exact pin here (for example
``ruff==0.17.2`` -> ``ruff==0.17.3``) while ``TPP_PINNED_REF`` still points at a
TPP revision carrying the old pin, pip fails with ``ResolutionImpossible``
(issues #1967 and #1973). This test names the conflicting package and the fix up front.

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
    return {canonicalize_name(req.name): req for req in map(Requirement, entries)}


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


@pytest.mark.parametrize(
    ("tpp_versions", "conflicting_tools"),
    [
        pytest.param(("0.17.2", "2.4.0", "9.1.1"), ("mypy", "pytest", "ruff"), id="old-tpp"),
        pytest.param(("0.17.2", "2.4.1", "9.2.0"), ("ruff",), id="ruff-only"),
        pytest.param(("0.17.3", "2.4.0", "9.2.0"), ("mypy",), id="mypy-only"),
        pytest.param(("0.17.3", "2.4.1", "9.1.1"), ("pytest",), id="pytest-only"),
        pytest.param(("0.17.3", "2.4.1", "9.2.0"), (), id="paired-update"),
    ],
)
def test_pinned_checkout_guard_reproduces_dev_tool_sync_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tpp_versions: tuple[str, str, str],
    conflicting_tools: tuple[str, ...],
) -> None:
    """Exercise the workflow entry point without needing a sibling checkout.

    Issue #1973's evidence run 41956043710 installed planner's updated pins
    with TPP acc4aed's old pins. TPP b56d92b carries the matching versions.
    Keep the historical versions fixed so later tool updates retain this regression.
    """
    planner_versions = ("0.17.3", "2.4.1", "9.2.0")
    tools = ("ruff", "mypy", "pytest")
    for directory, versions in ((tmp_path, planner_versions), (tmp_path / "tpp", tpp_versions)):
        directory.mkdir(exist_ok=True)
        pins = [f"{tool}=={version}" for tool, version in zip(tools, versions, strict=True)]
        (directory / "pyproject.toml").write_text(
            "[project]\ndependencies = []\n[project.optional-dependencies]\n" f"dev = {pins!r}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(f"{__name__}.REPO_ROOT", tmp_path)
    monkeypatch.setenv("TPP_REPO_PATH", "tpp")

    if not conflicting_tools:
        test_planner_dev_pins_resolve_with_pinned_tpp_checkout()
        return

    with pytest.raises(AssertionError, match="cannot be installed together") as failure:
        test_planner_dev_pins_resolve_with_pinned_tpp_checkout()

    diagnostics = str(failure.value)
    for tool, planner_version, tpp_version in zip(
        tools, planner_versions, tpp_versions, strict=True
    ):
        if tool in conflicting_tools:
            assert (
                f"{tool}: trip-planner '{tool}=={planner_version}' vs TPP '{tool}=={tpp_version}'"
                in diagnostics
            )
        else:
            assert f"{tool}: trip-planner" not in diagnostics
    assert (
        "Move TPP_PINNED_REF in .github/workflows/cross-repo-smoke.yml to a TPP "
        "revision with matching pins, in the same PR as the pin update."
    ) in diagnostics
