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
    requirements: dict[str, list[Requirement]] = {}
    for entries, extras in (
        (project.get("dependencies", []), ("", "dev")),
        (project.get("optional-dependencies", {}).get("dev", []), ("dev",)),
    ):
        for req in map(Requirement, entries):
            # Optional dev dependencies also have an implicit extra == 'dev'
            # condition; evaluating them in the base context admits inactive pins.
            if req.marker is not None and not any(
                req.marker.evaluate(environment={"extra": extra}) for extra in extras
            ):
                continue
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
@pytest.mark.parametrize("section", ["dependencies", "dev"])
@pytest.mark.parametrize(
    ("marker", "runtime_active", "dev_active"),
    [
        ("python_version < '3'", False, False),
        ("python_version >= '3'", True, True),
        ("extra == 'dev'", True, True),
        ("extra == 'test'", False, False),
        ("extra != 'dev'", True, False),
        ("extra == ''", True, False),
        ("python_version < '3' and extra == 'dev'", False, False),
        ("python_version >= '3' and extra != 'dev'", True, False),
    ],
)
def test_find_pin_conflicts_checks_active_dev_install_requirements(
    tmp_path: Path,
    constrained_project: str,
    section: str,
    marker: str,
    runtime_active: bool,
    dev_active: bool,
) -> None:
    """The smoke job installs base and dev requirements for the running Python."""
    projects = {name: tmp_path / f"{name}.toml" for name in ("planner", "tpp")}
    marked_requirement = f"ruff==0.17.4; {marker}"
    for name, path in projects.items():
        requirement = marked_requirement if name == constrained_project else "ruff==0.17.5"
        runtime = [requirement] if section == "dependencies" else []
        dev = [requirement] if section == "dev" else []
        path.write_text(
            f"[project]\ndependencies = {json.dumps(runtime)}\n"
            f"[project.optional-dependencies]\ndev = {json.dumps(dev)}\n",
            encoding="utf-8",
        )

    conflicts = find_pin_conflicts(projects["planner"], projects["tpp"])

    active = runtime_active if section == "dependencies" else dev_active
    if active:
        planner_req, tpp_req = (
            (marked_requirement, "ruff==0.17.5")
            if constrained_project == "planner"
            else ("ruff==0.17.5", marked_requirement)
        )
        assert conflicts == [
            f"ruff: trip-planner '{Requirement(planner_req)}' vs TPP '{Requirement(tpp_req)}'"
        ]
    else:
        assert conflicts == []


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
    assert producer.get("requires-python") == reviewed.get("requires-python"), (
        f"TPP requires-python snapshot differs from checkout {pinned_ref}; "
        "refresh the snapshot from the pinned source before recording verification."
    )
    for section, actual, expected in (
        ("runtime", producer["dependencies"], reviewed["dependencies"]),
        ("dev", producer["optional-dependencies"]["dev"], reviewed["optional-dependencies"]["dev"]),
    ):
        assert sorted(actual) == sorted(expected), (
            f"TPP {section} dependency snapshot differs from checkout {pinned_ref}; "
            "refresh the snapshot from the pinned source before recording verification."
        )


@pytest.mark.parametrize("mismatch", [None, "head", "runtime", "dev", "python", "missing-python"])
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
        '[project]\nrequires-python = ">=3.13"\ndependencies = ["httpx>=0.28.1"]\n'
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
    elif mismatch == "python":
        pyproject.write_text(metadata.replace(">=3.13", ">=3.13,<3.14"), encoding="utf-8")
    elif mismatch == "missing-python":
        (snapshot / "pyproject.toml").write_text(
            metadata.replace('requires-python = ">=3.13"\n', ""), encoding="utf-8"
        )
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


@pytest.mark.parametrize(
    "restored_pins",
    [
        pytest.param({"ruff": "0.17.2", "mypy": "2.4.0", "pytest": "9.1.1"}, id="all"),
        pytest.param({"ruff": "0.17.2"}, id="ruff"),
        pytest.param({"mypy": "2.4.0"}, id="mypy"),
        pytest.param({"pytest": "9.1.1"}, id="pytest"),
        pytest.param({"ruff": "0.17.4"}, id="issue-2038-stale-ruff"),
    ],
)
def test_offline_workflow_guard_rejects_original_producer_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, restored_pins: dict[str, str]
) -> None:
    """The actual offline gate must catch an unpaired sync without a live checkout."""
    test_workflow_tpp_pin_resolves_with_planner_dev_pins(monkeypatch)

    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "cross-repo-smoke.yml").read_text()
    )
    pinned_ref = workflow["env"]["TPP_PINNED_REF"]
    producer = REPO_ROOT / "tests" / "fixtures" / "tpp_dev_pins" / pinned_ref / "pyproject.toml"
    metadata = producer.read_text(encoding="utf-8")
    producer_requirements = _requirements(producer)
    planner = REPO_ROOT / "pyproject.toml"
    planner_requirements = _requirements(planner)
    for tool, version in restored_pins.items():
        current = str(producer_requirements[tool][0])
        assert current in metadata
        metadata = metadata.replace(current, f"{tool}=={version}")

    # Preserve real planner requirements and the workflow's snapshot selection;
    # change only the producer pins that caused the reported installation failure.
    (tmp_path / "pyproject.toml").write_bytes(planner.read_bytes())
    workflow_directory = tmp_path / ".github" / "workflows"
    workflow_directory.mkdir(parents=True)
    (workflow_directory / "cross-repo-smoke.yml").write_text(
        yaml.safe_dump({"env": {"TPP_PINNED_REF": pinned_ref}}), encoding="utf-8"
    )
    snapshot = tmp_path / "tests" / "fixtures" / "tpp_dev_pins" / pinned_ref
    snapshot.mkdir(parents=True)
    (snapshot / "pyproject.toml").write_text(metadata, encoding="utf-8")
    monkeypatch.setattr(f"{__name__}.REPO_ROOT", tmp_path)
    monkeypatch.delenv("TPP_REPO_PATH", raising=False)

    with pytest.raises(AssertionError, match="cannot be installed together") as failure:
        test_workflow_tpp_pin_resolves_with_planner_dev_pins(monkeypatch)

    for tool, version in restored_pins.items():
        planner_pin = planner_requirements[tool][0]
        assert f"{tool}: trip-planner '{planner_pin}' vs TPP '{tool}=={version}'" in str(
            failure.value
        )


@pytest.mark.parametrize(
    ("planner_fixture", "producer_ref", "conflicting_tools"),
    [
        pytest.param(
            "issue_2025_ledger/failed-trip-planner.toml",
            "acc4aeddee5f4ffefbdc73fcb07505cd3d198197",
            ("mypy", "pytest", "ruff"),
            id="original-install-inputs",
        ),
        pytest.param(
            "issue_2025_ledger/failed-trip-planner.toml",
            "b56d92b389736c70370aa9134f379ac8cd1f3ad1",
            (),
            id="change-only-tpp-checkout",
        ),
        pytest.param(
            "issue_2025_ledger/successful-trip-planner.toml",
            "b56d92b389736c70370aa9134f379ac8cd1f3ad1",
            (),
            id="merged-install-inputs",
        ),
        pytest.param(
            "issue_2038_dev_pins/trip-planner.toml",
            "5c9ec6e15ac959023b9fc9cdd1099d70a6073396",
            ("ruff",),
            id="issue-2038-original-install",
        ),
        pytest.param(
            "issue_2038_dev_pins/trip-planner.toml",
            "50992156e4a1f97c1115b6c7af84a219a3b9aae7",
            (),
            id="issue-2038-repaired-install",
        ),
    ],
)
@pytest.mark.parametrize("guard", ["live-checkout", "workflow-snapshot"])
def test_smoke_pin_guard_with_historical_editable_checkouts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    planner_fixture: str,
    producer_ref: str,
    conflicting_tools: tuple[str, ...],
    guard: str,
) -> None:
    """Both guard entry points must reject the old source and accept its replacement."""
    planner_source = REPO_ROOT / "tests/fixtures" / planner_fixture
    producer_source = REPO_ROOT / "tests/fixtures/tpp_dev_pins" / producer_ref / "pyproject.toml"
    # Preserve both complete original metadata files, including runtime and dev
    # requirements. Each repair changes only the selected producer source.
    (tmp_path / "pyproject.toml").write_bytes(planner_source.read_bytes())
    checkout = tmp_path / "tpp"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_bytes(producer_source.read_bytes())
    monkeypatch.setattr(f"{__name__}.REPO_ROOT", tmp_path)

    def run_guard() -> None:
        if guard == "live-checkout":
            test_planner_dev_pins_resolve_with_pinned_tpp_checkout()
        else:
            test_workflow_tpp_pin_resolves_with_planner_dev_pins(monkeypatch)

    if guard == "live-checkout":
        monkeypatch.setenv("TPP_REPO_PATH", "tpp")
    else:
        workflow_directory = tmp_path / ".github" / "workflows"
        workflow_directory.mkdir(parents=True)
        (workflow_directory / "cross-repo-smoke.yml").write_text(
            yaml.safe_dump({"env": {"TPP_PINNED_REF": producer_ref}}), encoding="utf-8"
        )
        snapshot = tmp_path / "tests" / "fixtures" / "tpp_dev_pins" / producer_ref
        snapshot.mkdir(parents=True)
        (snapshot / "pyproject.toml").write_bytes(producer_source.read_bytes())
        # An inherited checkout must not override the workflow's selected source.
        monkeypatch.setenv("TPP_REPO_PATH", str(tmp_path / "missing-checkout"))

    if conflicting_tools:
        with pytest.raises(AssertionError, match="cannot be installed together") as failure:
            run_guard()
        diagnostics = str(failure.value)
        for tool in ("ruff", "mypy", "pytest"):
            assert (f"{tool}: trip-planner" in diagnostics) == (tool in conflicting_tools)
        assert "Move TPP_PINNED_REF" in diagnostics
    else:
        run_guard()


@pytest.mark.parametrize(
    ("producer_ref", "expected_exit"),
    [
        pytest.param("5c9ec6e15ac959023b9fc9cdd1099d70a6073396", 1, id="original-producer"),
        pytest.param("50992156e4a1f97c1115b6c7af84a219a3b9aae7", 0, id="repaired-producer"),
    ],
)
@pytest.mark.parametrize(
    "guard_mode", ["live-checkout", "workflow-snapshot", "missing-snapshot", "combined-guards"]
)
def test_pin_guard_cli_with_issue_2038_checkouts(
    tmp_path: Path, producer_ref: str, expected_exit: int, guard_mode: str
) -> None:
    """Both pytest guards must reject #2037's old pair and unreviewed source pins."""
    planner = REPO_ROOT / "tests/fixtures/issue_2038_dev_pins/trip-planner.toml"
    producer = REPO_ROOT / "tests/fixtures/tpp_dev_pins" / producer_ref / "pyproject.toml"
    (tmp_path / "pyproject.toml").write_bytes(planner.read_bytes())
    checkout = tmp_path / "tpp"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_bytes(producer.read_bytes())
    guard = tmp_path / "tests/scripts/test_cross_repo_dev_pins.py"
    guard.parent.mkdir(parents=True)
    guard.write_bytes(Path(__file__).read_bytes())
    test_names = ["test_planner_dev_pins_resolve_with_pinned_tpp_checkout"]
    if guard_mode != "live-checkout":
        snapshot_test = "test_workflow_tpp_pin_resolves_with_planner_dev_pins"
        if guard_mode == "combined-guards":
            test_names.append(snapshot_test)
        else:
            test_names = [snapshot_test]
        workflow = tmp_path / ".github/workflows/cross-repo-smoke.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text(
            yaml.safe_dump({"env": {"TPP_PINNED_REF": producer_ref}}), encoding="utf-8"
        )
        if guard_mode in ("workflow-snapshot", "combined-guards"):
            snapshot = tmp_path / "tests/fixtures/tpp_dev_pins" / producer_ref / "pyproject.toml"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_bytes(producer.read_bytes())
        else:
            expected_exit = 1

    # A fresh pytest process exercises collection, checkout discovery and failure
    # propagation, without inheriting the parent process's monkeypatches or config.
    environment = _checkout_git_env()
    environment["TPP_REPO_PATH"] = "tpp"
    environment["PYTEST_ADDOPTS"] = ""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *(f"tests/scripts/test_cross_repo_dev_pins.py::{name}" for name in test_names),
            "-q",
            "-m",
            "not slow",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    diagnostics = result.stdout + result.stderr
    assert result.returncode == expected_exit, diagnostics
    if expected_exit:
        assert f"{len(test_names)} failed" in diagnostics
    if guard_mode == "missing-snapshot":
        # Even a compatible live checkout cannot replace review of a new pin.
        assert f"Missing TPP dependency snapshot for {producer_ref}" in diagnostics
        assert "cannot be installed together" not in diagnostics
    elif expected_exit:
        assert "cannot be installed together" in diagnostics
        assert "ruff: trip-planner 'ruff==0.17.5' vs TPP 'ruff==0.17.4'" in diagnostics
        assert "mypy: trip-planner" not in diagnostics
        assert "pytest: trip-planner" not in diagnostics
    else:
        assert f"{len(test_names)} passed" in diagnostics


@pytest.mark.parametrize(
    ("restored_tool", "historical_phase"),
    [
        *((tool, None) for tool in ("all", "ruff", "mypy", "pytest", None)),
        pytest.param("ruff-2017", None, id="issue-2017-producer"),
        pytest.param("ruff-2038", None, id="issue-2038-producer"),
        pytest.param(None, "failed", id="issue-2006-failed-install"),
        pytest.param(None, "successful", id="issue-2006-successful-install"),
        pytest.param(None, "issue-2038-failed", id="issue-2038-original-install"),
        pytest.param(None, "issue-2038-repaired", id="issue-2038-repaired-install"),
    ],
)
@pytest.mark.parametrize("target_python", ["3.13", "3.14"])
def test_pip_resolves_paired_dev_tool_pins_offline(
    tmp_path: Path, restored_tool: str | None, historical_phase: str | None, target_python: str
) -> None:
    """Exercise pip's resolver for the failing tool pins without network or installs.

    Metadata-only wheels isolate the tools reported in #1973, #2017 and #2038. The passing
    case reads the real planner requirements and the snapshot selected by the
    workflow; failing cases restore all or one of the producer's original pins.
    Both projects declare the tools in their dev extras, matching the joint
    installation in the workflow rather than supplying tools as root requirements.
    Historical cases read fixed source snapshots, independent of subsequent
    planner and workflow updates. For #2038, only the TPP revision changes
    between the failed and repaired installations.
    Resolve for both CI Python versions, preserving the source projects' Python
    requirements rather than relying on whichever interpreter runs this test.
    This verifies resolution only, not a complete cross-repo installation.
    """
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "cross-repo-smoke.yml").read_text()
    )
    snapshot = REPO_ROOT / "tests" / "fixtures" / "tpp_dev_pins" / workflow["env"]["TPP_PINNED_REF"]
    planner = REPO_ROOT / "pyproject.toml"
    historical_failure = historical_phase in ("failed", "issue-2038-failed")
    if historical_phase is not None:
        # #2006 uses the editable checkouts in runs 42449207754 / 42484305260;
        # #2038 preserves sync PR #2037's planner metadata at head 65b25b559ea6.
        planner_fixture, producer_ref = {
            "failed": (
                "issue_2025_ledger/failed-trip-planner.toml",
                "acc4aeddee5f4ffefbdc73fcb07505cd3d198197",
            ),
            "successful": (
                "issue_2025_ledger/successful-trip-planner.toml",
                "b56d92b389736c70370aa9134f379ac8cd1f3ad1",
            ),
            "issue-2038-failed": (
                "issue_2038_dev_pins/trip-planner.toml",
                "5c9ec6e15ac959023b9fc9cdd1099d70a6073396",
            ),
            "issue-2038-repaired": (
                "issue_2038_dev_pins/trip-planner.toml",
                "50992156e4a1f97c1115b6c7af84a219a3b9aae7",
            ),
        }[historical_phase]
        snapshot = REPO_ROOT / "tests/fixtures/tpp_dev_pins" / producer_ref
        planner = REPO_ROOT / "tests/fixtures" / planner_fixture
    if restored_tool in ("ruff-2017", "ruff-2038"):
        # These are the actual producers from the failed sync deliveries. Their
        # mypy and pytest pins already matched planner; only Ruff was incompatible.
        producer_ref = {
            "ruff-2017": "b56d92b389736c70370aa9134f379ac8cd1f3ad1",
            "ruff-2038": "5c9ec6e15ac959023b9fc9cdd1099d70a6073396",
        }[restored_tool]
        snapshot = REPO_ROOT / "tests/fixtures/tpp_dev_pins" / producer_ref
    old_versions = {"ruff": "0.17.2", "mypy": "2.4.0", "pytest": "9.1.1"}
    projects = {
        "planner": _requirements(planner),
        "tpp": _requirements(snapshot / "pyproject.toml"),
    }
    project_metadata = {
        "planner": tomllib.loads(planner.read_text(encoding="utf-8"))["project"],
        "tpp": tomllib.loads((snapshot / "pyproject.toml").read_text(encoding="utf-8"))["project"],
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
        if requires_python := project_metadata[name].get("requires-python"):
            dependency_metadata += f"Requires-Python: {requires_python}\n"
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

    # Supply original, planner and producer candidates so a failure proves
    # conflicting requirements, rather than a missing wheel in the offline index.
    for tool, old_version in old_versions.items():
        current_version = _exact_pin(projects["planner"][tool][0])
        assert current_version is not None
        producer_version = _exact_pin(projects["tpp"][tool][0])
        assert producer_version is not None
        for version in {old_version, current_version, producer_version}:
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
            "--python-version",
            target_python,
            "--only-binary=:all:",
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
    if restored_tool is not None or historical_failure:
        assert result.returncode != 0, diagnostics
        assert "ResolutionImpossible" in diagnostics
        if restored_tool in ("all", "ruff-2017", "ruff-2038") or historical_failure:
            tool = "ruff"
        else:
            # The enclosing condition means this branch is reachable only for
            # a named restored tool, but mypy cannot infer that relationship.
            assert restored_tool is not None
            tool = restored_tool
        producer_requirement = (
            str(projects["tpp"][tool][0])
            if historical_phase is not None or restored_tool in ("ruff-2017", "ruff-2038")
            else f"{tool}=={old_versions[tool]}"
        )
        assert producer_requirement in diagnostics
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
        resolved_metadata = {
            canonicalize_name(entry["metadata"]["name"]): entry["metadata"] for entry in resolved
        }
        for name, distribution in project_names.items():
            assert resolved_metadata[canonicalize_name(distribution)].get("requires_python") == (
                project_metadata[name].get("requires-python")
            )


@pytest.mark.parametrize(
    ("tpp_versions", "planner_versions", "conflicting_tools"),
    [
        pytest.param(
            ("0.17.2", "2.4.0", "9.1.1"),
            ("0.17.3", "2.4.1", "9.2.0"),
            ("mypy", "pytest", "ruff"),
            id="old-tpp",
        ),
        pytest.param(
            ("0.17.2", "2.4.1", "9.2.0"), ("0.17.3", "2.4.1", "9.2.0"), ("ruff",), id="ruff-only"
        ),
        pytest.param(
            ("0.17.3", "2.4.0", "9.2.0"), ("0.17.3", "2.4.1", "9.2.0"), ("mypy",), id="mypy-only"
        ),
        pytest.param(
            ("0.17.3", "2.4.1", "9.1.1"),
            ("0.17.3", "2.4.1", "9.2.0"),
            ("pytest",),
            id="pytest-only",
        ),
        pytest.param(
            ("0.17.3", "2.4.1", "9.2.0"), ("0.17.3", "2.4.1", "9.2.0"), (), id="paired-update"
        ),
        pytest.param(
            ("0.17.3", "2.4.1", "9.2.0"), ("0.17.4", "2.4.1", "9.2.0"), ("ruff",), id="ruff-2017"
        ),
    ],
)
def test_pinned_checkout_guard_reproduces_dev_tool_sync_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tpp_versions: tuple[str, str, str],
    planner_versions: tuple[str, str, str],
    conflicting_tools: tuple[str, ...],
) -> None:
    """Exercise the workflow entry point without needing a sibling checkout.

    Issue #1973's evidence run 41956043710 installed planner's updated pins
    with TPP acc4aed's old pins. TPP b56d92b carries the matching versions.
    Issue #2017 reproduces the ruff 0.17.3 -> 0.17.4 sync conflict.
    Keep the historical versions fixed so later tool updates retain this regression.
    """
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
