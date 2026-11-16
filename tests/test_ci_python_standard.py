"""Keep repository-owned CI callers on the owner's tested Python standard."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import tomllib
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
RUNTIME_KEYS = {
    "python-version",
    "python-versions",
    "primary-python-version",
    "coverage-python-version",
    "PYTHON_VERSION",
    "COVERAGE_REFERENCE_RUNTIME",
}


def _runtime_pins(node: Any, location: str) -> Iterator[tuple[str, Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{location}.{key}"
            if key in RUNTIME_KEYS:
                yield path, value
            yield from _runtime_pins(value, path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _runtime_pins(value, f"{location}[{index}]")


def _contains_old_runtime(value: Any) -> bool:
    if isinstance(value, list):
        return any(_contains_old_runtime(item) for item in value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            pass
        else:
            if decoded != value:
                return _contains_old_runtime(decoded)
    return str(value) == "3.12" or str(value).startswith("3.12.")


def test_workflow_python_pins_follow_standard() -> None:
    workflows = {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(WORKFLOWS.iterdir())
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    }
    assert workflows, "No workflow YAML was inspected"
    offenders = [
        location
        for filename, workflow in workflows.items()
        for location, value in _runtime_pins(workflow, filename)
        if _contains_old_runtime(value)
    ]
    assert not offenders, f"Python 3.12 runtime pins remain: {offenders}"
    for filename, job in (("ci.yml", "python"), ("pr-00-gate.yml", "python-ci")):
        config = workflows[filename]["jobs"][job]
        assert json.loads(config["with"]["python-versions"]) == ["3.13", "3.14"]
        assert config["with"]["primary-python-version"] == "3.14"
        assert not config.get("continue-on-error", False)


def _pyproject_defines_ruff_config(pyproject: Path) -> bool:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return "ruff" in data.get("tool", {})


def test_ruff_check_matches_reusable_python_ci_when_ruff_omitted() -> None:
    """When pyproject.toml has no [tool.ruff], CI uses --select E4,E7,E9,F (not the default set)."""
    pyproject = ROOT / "pyproject.toml"
    assert not _pyproject_defines_ruff_config(pyproject), "update this test if [tool.ruff] is added"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "E4,E7,E9,F",
            "--extend-exclude",
            ".workflows-lib",
            ".",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_mypy_matches_reusable_python_ci() -> None:
    """Reusable Python CI runs mypy with pyproject config and .workflows-lib excluded.

    Local ``build/`` output is excluded rather than deleted so developer artifacts survive.
    """
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            "pyproject.toml",
            "--exclude",
            r"(^|/)(?:\.workflows-lib|build)(?:/|$)",
            ".",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_make_test_matches_reusable_python_ci_pytest() -> None:
    """Reusable Python CI on PR head runs ``python -m pytest``; ``make test`` must match."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    recipe: list[str] = []
    in_test_target = False
    for line in makefile.splitlines():
        if line.startswith("test:"):
            in_test_target = True
            continue
        if not in_test_target:
            continue
        if line.startswith("\t"):
            recipe.append(line.strip())
            continue
        if line.strip():
            break
    assert recipe == ["python -m pytest"], f"Makefile test target recipe mismatch: {recipe!r}"


def test_black_format_matches_pre_commit_gate() -> None:
    """Keepalive and pre-commit Black gate: line length 100, exclude workflows-lib and node_modules."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "black",
            "--check",
            "--line-length",
            "100",
            "--exclude",
            r"(\.workflows-lib|node_modules)",
            ".",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_cross_repo_full_product_offline_guards_match_pr_head() -> None:
    """Cross-repo smoke job pin/runtime checks must pass offline before hosted CI is trusted."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/scripts/test_cross_repo_smoke_workflow.py",
            "tests/scripts/test_cross_repo_dev_pins.py",
            "-q",
            "-m",
            "not slow",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
