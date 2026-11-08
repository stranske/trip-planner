"""Keep renderer and all script regressions in the repository's default test run."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_default_collection_includes_html_and_script_regressions() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=root,
        env={**os.environ, "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    collected = set(result.stdout.splitlines())
    expected = {
        "tests/test_build_html.py::test_build_html_executes[trips]",
        "tests/test_build_html.py::test_build_html_executes[empty]",
        "tests/scripts/test_cross_repo_dev_pins.py::test_live_tpp_checkout_matches_workflow_snapshot",
        (
            "tests/scripts/test_cross_repo_smoke_workflow.py"
            "::test_workflow_checks_live_dev_pins_before_joint_install"
        ),
    }
    assert expected <= collected, f"Default collection omits required tests: {expected - collected}"

    # Explicit file selection bypasses directory-level collection filters. Compare
    # real nodes so an allowlist cannot silently remove entire script modules.
    script_files = sorted((root / "tests" / "scripts").glob("test_*.py"))
    assert script_files, "No script regression files found"
    scripts = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *map(str, script_files)],
        cwd=root,
        env={**os.environ, "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert scripts.returncode == 0, scripts.stdout + scripts.stderr
    script_nodes = {line for line in scripts.stdout.splitlines() if "::" in line}
    assert script_nodes, scripts.stdout
    missing = script_nodes - collected
    assert not missing, f"Default collection omits script regressions: {sorted(missing)}"
