"""Keep every test module in the repository's default test run."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_default_collection_includes_all_regressions() -> None:
    """Require default collection to retain all explicitly discoverable nodes."""
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "tests.collection_audit", "--collect-only", "-q"],
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
    # real nodes so an allowlist cannot silently remove modules in any test directory.
    test_files = sorted(
        set((root / "tests").rglob("test_*.py")) | set((root / "tests").rglob("*_test.py"))
    )
    assert test_files, "No regression files found"
    explicit = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "tests.collection_audit",
            "--collect-only",
            "-q",
            *map(str, test_files),
        ],
        cwd=root,
        env={**os.environ, "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert explicit.returncode == 0, explicit.stdout + explicit.stderr
    explicit_nodes = {line for line in explicit.stdout.splitlines() if "::" in line}
    assert explicit_nodes, explicit.stdout
    missing = explicit_nodes - collected
    assert not missing, f"Default collection omits regressions: {sorted(missing)}"
