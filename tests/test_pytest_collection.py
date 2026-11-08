"""Keep renderer and dev-pin regressions in the repository's default test run."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_default_collection_includes_html_and_pin_regressions() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=Path(__file__).resolve().parents[1],
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
