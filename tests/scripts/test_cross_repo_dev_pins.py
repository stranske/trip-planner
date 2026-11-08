"""Dev-tool pins must co-resolve with the pinned Travel-Plan-Permission checkout.

The cross-repo smoke job installs ``TPP[dev]`` and ``trip-planner[dev]`` into one
interpreter. When a dev-tool sync bumps an exact pin here (for example
``ruff==0.17.2`` -> ``ruff==0.17.3``) while ``TPP_PINNED_REF`` still points at a
TPP revision carrying the old pin, pip fails with ``ResolutionImpossible``
(issues #1967 and #1973). This test names the conflicting package and the fix up front.

The offline regression checks the workflow's actual pin against a reviewed
producer dependency snapshot. The live checkout check additionally needs
``TPP_REPO_PATH`` (the smoke workflow sets it). Run with
``TPP_REPO_PATH=../Travel-Plan-Permission pytest tests/scripts/test_cross_repo_dev_pins.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from itertools import product
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml
from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parents[2]


def _checkout_git_env() -> dict[str, str]:
    """Use the requested checkout while preserving unrelated Git configuration."""
    repository_variables = {
        "GIT_DIR",
        "GIT_COMMON_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE",
        "GIT_SHALLOW_FILE",
    }
    return {key: value for key, value in os.environ.items() if key not in repository_variables}


def _requirements(pyproject: Path) -> dict[str, list[Requirement]]:
    project = tomllib.loads(pyproject.read_text())["project"]
    entries = list(project.get("dependencies", []))
    entries += project.get("optional-dependencies", {}).get("dev", [])
    requirements: dict[str, list[Requirement]] = {}
    for req in map(Requirement, entries):
        requirements.setdefault(canonicalize_name(req.name), []).append(req)
    return requirements


def _exact_pin(req: Requirement) -> str | None:
    for spec in req.specifier:
        if spec.operator == "==" and not spec.version.endswith(".*"):
            return spec.version
    return None


def find_pin_conflicts(planner_pyproject: Path, tpp_pyproject: Path) -> list[str]:
    """Return one message per package whose exact pin the other side rejects."""
    planner = _requirements(planner_pyproject)
    tpp = _requirements(tpp_pyproject)
    conflicts = []
    for name in sorted(planner.keys() & tpp.keys()):
        for planner_req, tpp_req in product(planner[name], tpp[name]):
            if any(
                (version := _exact_pin(pinned)) is not None
                and not other.specifier.contains(version, prereleases=True)
                for pinned, other in ((planner_req, tpp_req), (tpp_req, planner_req))
            ):
                conflicts.append(f"{name}: trip-planner '{planner_req}' vs TPP '{tpp_req}'")
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


@pytest.mark.parametrize("constrained_project", ["planner", "tpp"])
@pytest.mark.parametrize(
    ("constraint", "other_requirement", "conflicting"),
    [
        pytest.param("ruff==0.17.2,>=0.17", "ruff>=0.17.3", True, id="conflicting-compound-pin"),
        pytest.param("ruff==0.17.3,>=0.17", "ruff>=0.17.3", False, id="matching-compound-pin"),
        pytest.param("ruff==0.16.*", "ruff==0.17.3", True, id="conflicting-prefix"),
        pytest.param("ruff==0.17.*", "ruff==0.17.3", False, id="matching-prefix"),
    ],
)
def test_find_pin_conflicts_checks_compound_and_prefix_constraints(
    tmp_path: Path,
    constrained_project: str,
    constraint: str,
    other_requirement: str,
    conflicting: bool,
) -> None:
    """A range beside an exact pin must not hide the co-install conflict."""
    projects = {name: tmp_path / f"{name}.toml" for name in ("planner", "tpp")}
    requirements = {
        name: constraint if name == constrained_project else other_requirement for name in projects
    }
    for name, path in projects.items():
        path.write_text(
            "[project]\ndependencies = []\n[project.optional-dependencies]\n"
            f"dev = {[requirements[name]]!r}\n",
            encoding="utf-8",
        )

    conflicts = find_pin_conflicts(projects["planner"], projects["tpp"])

    expected = (
        [
            (
                f"ruff: trip-planner '{Requirement(requirements['planner'])}' "
                f"vs TPP '{Requirement(requirements['tpp'])}'"
            )
        ]
        if conflicting
        else []
    )
    assert conflicts == expected


@pytest.mark.parametrize("constrained_project", ["planner", "tpp"])
@pytest.mark.parametrize("runtime_pin", ["0.17.2", "0.17.3"])
def test_find_pin_conflicts_preserves_runtime_and_dev_requirements(
    tmp_path: Path, constrained_project: str, runtime_pin: str
) -> None:
    """Installing [dev] keeps runtime constraints, even for repeated packages."""
    projects = {name: tmp_path / f"{name}.toml" for name in ("planner", "tpp")}
    for name, path in projects.items():
        runtime = [f"ruff=={runtime_pin}"] if name == constrained_project else []
        dev = ["ruff>=0.17"] if name == constrained_project else ["ruff==0.17.3"]
        path.write_text(
            f"[project]\ndependencies = {runtime!r}\n"
            f"[project.optional-dependencies]\ndev = {dev!r}\n",
            encoding="utf-8",
        )

    conflicts = find_pin_conflicts(projects["planner"], projects["tpp"])

    if runtime_pin == "0.17.3":
        assert conflicts == []
    else:
        planner_pin, tpp_pin = (
            (runtime_pin, "0.17.3") if constrained_project == "planner" else ("0.17.3", runtime_pin)
        )
        assert conflicts == [f"ruff: trip-planner 'ruff=={planner_pin}' vs TPP 'ruff=={tpp_pin}'"]


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


def test_live_tpp_checkout_matches_workflow_snapshot() -> None:
    """Keep local verification tied to the producer revision used by the gate."""
    tpp_repo = os.environ.get("TPP_REPO_PATH")
    if not tpp_repo:
        pytest.skip("TPP_REPO_PATH not set; the cross-repo smoke workflow provides it")
    checkout = (REPO_ROOT / tpp_repo).resolve()
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "cross-repo-smoke.yml").read_text()
    )
    pinned_ref = workflow["env"]["TPP_PINNED_REF"]
    resolved = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
        env=_checkout_git_env(),
    ).stdout.strip()
    assert resolved == pinned_ref, (
        f"TPP checkout HEAD {resolved} does not match TPP_PINNED_REF {pinned_ref}. "
        "Check out the workflow's pinned revision before recording live verification."
    )
    snapshot = REPO_ROOT / "tests" / "fixtures" / "tpp_dev_pins" / pinned_ref / "pyproject.toml"
    producer = tomllib.loads((checkout / "pyproject.toml").read_text())["project"]
    reviewed = tomllib.loads(snapshot.read_text())["project"]
    for section, actual, expected in (
        ("runtime", producer["dependencies"], reviewed["dependencies"]),
        ("dev", producer["optional-dependencies"]["dev"], reviewed["optional-dependencies"]["dev"]),
    ):
        assert sorted(actual) == sorted(expected), (
            f"TPP {section} dependency snapshot differs from checkout {pinned_ref}; "
            "refresh the snapshot from the pinned source before recording verification."
        )


@pytest.mark.parametrize("mismatch", [None, "head", "runtime", "dev"])
@pytest.mark.parametrize("inherit_git_locations", [False, True])
def test_live_snapshot_guard_rejects_unverified_producer_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str | None,
    inherit_git_locations: bool,
) -> None:
    """Matching dev pins alone cannot establish that the pinned source was tested."""
    if inherit_git_locations:
        for key, value in {
            "GIT_DIR": str(tmp_path / "outer.git"),
            "GIT_COMMON_DIR": str(tmp_path / "common.git"),
            "GIT_WORK_TREE": str(tmp_path / "outer"),
            "GIT_INDEX_FILE": str(tmp_path / "outer.index"),
            "GIT_OBJECT_DIRECTORY": str(tmp_path / "objects"),
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(tmp_path / "alternates"),
            "GIT_NAMESPACE": "outer",
            "GIT_SHALLOW_FILE": str(tmp_path / "outer.shallow"),
        }.items():
            monkeypatch.setenv(key, value)
    checkout = tmp_path / "tpp"
    checkout.mkdir()
    pyproject = checkout / "pyproject.toml"
    metadata = (
        '[project]\ndependencies = ["httpx>=0.28.1"]\n'
        '[project.optional-dependencies]\ndev = ["ruff==0.17.3"]\n'
    )
    pyproject.write_text(metadata, encoding="utf-8")
    for command in (
        ["init", "--quiet"],
        ["add", "pyproject.toml"],
        [
            "-c",
            "user.name=Pin regression",
            "-c",
            "user.email=pins@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Producer snapshot",
        ],
    ):
        subprocess.run(
            ["git", "-C", str(checkout), *command],
            check=True,
            timeout=10,
            env=_checkout_git_env(),
        )
    pinned_ref = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        text=True,
        timeout=10,
        env=_checkout_git_env(),
    ).strip()
    workflow_directory = tmp_path / ".github" / "workflows"
    workflow_directory.mkdir(parents=True)
    workflow_ref = "0" * 40 if mismatch == "head" else pinned_ref
    (workflow_directory / "cross-repo-smoke.yml").write_text(
        yaml.safe_dump({"env": {"TPP_PINNED_REF": workflow_ref}}), encoding="utf-8"
    )
    snapshot = tmp_path / "tests" / "fixtures" / "tpp_dev_pins" / pinned_ref
    snapshot.mkdir(parents=True)
    (snapshot / "pyproject.toml").write_text(metadata, encoding="utf-8")
    if mismatch == "runtime":
        pyproject.write_text(metadata.replace("httpx>=0.28.1", "httpx>=0.29"), encoding="utf-8")
    elif mismatch == "dev":
        pyproject.write_text(metadata.replace("ruff==0.17.3", "ruff==0.17.2"), encoding="utf-8")
    monkeypatch.setattr(f"{__name__}.REPO_ROOT", tmp_path)
    monkeypatch.setenv("TPP_REPO_PATH", "tpp")

    if mismatch is None:
        test_live_tpp_checkout_matches_workflow_snapshot()
    else:
        message = "does not match TPP_PINNED_REF" if mismatch == "head" else "snapshot differs"
        with pytest.raises(AssertionError, match=message):
            test_live_tpp_checkout_matches_workflow_snapshot()


def test_workflow_tpp_pin_resolves_with_planner_dev_pins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the paired pin update locally even without a sibling checkout.

    Unlike synthetic matching-version cases, this checks the repository's
    real planner requirements and workflow ref. The producer snapshot contains
    the dependency sections from that exact commit, so updating dev pins alone
    must fail here before pip attempts the cross-repo installation.
    """
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "cross-repo-smoke.yml").read_text()
    )
    pinned_ref = workflow["env"]["TPP_PINNED_REF"]
    snapshot = REPO_ROOT / "tests" / "fixtures" / "tpp_dev_pins" / pinned_ref
    assert (snapshot / "pyproject.toml").is_file(), (
        f"Missing TPP dependency snapshot for {pinned_ref}. Copy the dependencies "
        "and dev extra from the pinned producer's pyproject.toml into "
        f"{snapshot / 'pyproject.toml'} when reviewing a TPP pin update."
    )
    monkeypatch.setenv("TPP_REPO_PATH", str(snapshot))

    test_planner_dev_pins_resolve_with_pinned_tpp_checkout()


@pytest.mark.parametrize("restored_tool", ["all", "ruff", "mypy", "pytest", None])
def test_pip_resolves_paired_dev_tool_pins_offline(
    tmp_path: Path, restored_tool: str | None
) -> None:
    """Exercise pip's resolver for the failing tool pins without network or installs.

    Metadata-only wheels isolate the three tools reported in #1973. The passing
    case reads the real planner requirements and the snapshot selected by the
    workflow; failing cases restore all or one of the producer's original pins.
    Both projects declare the tools in their dev extras, matching the joint
    installation in the workflow rather than supplying tools as root requirements.
    This verifies resolution only, not a complete cross-repo installation.
    """
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "cross-repo-smoke.yml").read_text()
    )
    snapshot = REPO_ROOT / "tests" / "fixtures" / "tpp_dev_pins" / workflow["env"]["TPP_PINNED_REF"]
    old_versions = {"ruff": "0.17.2", "mypy": "2.4.0", "pytest": "9.1.1"}
    projects = {
        "planner": _requirements(REPO_ROOT / "pyproject.toml"),
        "tpp": _requirements(snapshot / "pyproject.toml"),
    }

    def write_wheel(name: str, version: str, dependency_metadata: str = "") -> None:
        dist_info = f"{name}-{version}.dist-info"
        with ZipFile(tmp_path / f"{name}-{version}-py3-none-any.whl", "w") as wheel:
            wheel.writestr(
                f"{dist_info}/METADATA",
                f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n" + dependency_metadata,
            )
            wheel.writestr(
                f"{dist_info}/WHEEL",
                "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            )
            wheel.writestr(f"{dist_info}/RECORD", "")

    project_names = {"planner": "trip_planner", "tpp": "travel_plan_permission"}
    for name, requirements in projects.items():
        dependency_metadata = "Provides-Extra: dev\n"
        for tool, old_version in old_versions.items():
            selected = requirements[tool]
            if name == "tpp" and restored_tool in ("all", tool):
                selected = [Requirement(f"{tool}=={old_version}")]
            for original in selected:
                req = Requirement(str(original))
                req.marker = Marker(
                    f'({req.marker}) and extra == "dev"' if req.marker else 'extra == "dev"'
                )
                dependency_metadata += f"Requires-Dist: {req}\n"
        write_wheel(project_names[name], "0.1.0", dependency_metadata)

    # Supply both old and current candidates so a failure proves conflicting
    # requirements, rather than a missing wheel in the offline index.
    for tool, old_version in old_versions.items():
        current_version = _exact_pin(projects["planner"][tool][0])
        assert current_version is not None
        for version in {old_version, current_version}:
            write_wheel(tool, version)

    report = tmp_path / "resolution.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "--isolated",
            "--disable-pip-version-check",
            "install",
            "--dry-run",
            "--ignore-installed",
            "--no-index",
            "--no-cache-dir",
            "--find-links",
            str(tmp_path),
            "--report",
            str(report),
            *(f"{name}[dev]==0.1.0" for name in project_names.values()),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    diagnostics = result.stdout + result.stderr
    if restored_tool is not None:
        assert result.returncode != 0, diagnostics
        assert "ResolutionImpossible" in diagnostics
        tool = "ruff" if restored_tool == "all" else restored_tool
        assert f"{tool}=={old_versions[tool]}" in diagnostics
        assert str(projects["planner"][tool][0]) in diagnostics
        assert "trip-planner[dev]" in diagnostics
        assert "travel-plan-permission[dev]" in diagnostics
    else:
        assert result.returncode == 0, diagnostics
        resolved = json.loads(report.read_text(encoding="utf-8"))["install"]
        expected: dict[str, str | None] = {
            tool: _exact_pin(projects["planner"][tool][0]) for tool in old_versions
        }
        expected.update({canonicalize_name(name): "0.1.0" for name in project_names.values()})
        assert {
            canonicalize_name(entry["metadata"]["name"]): entry["metadata"]["version"]
            for entry in resolved
        } == expected


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
