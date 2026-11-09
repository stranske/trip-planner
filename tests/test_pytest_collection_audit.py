"""Exercise collection auditing independently of the repository's test suite."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("operation", ["pass", "items.reverse()", "items.pop()"])
def test_collection_audit_detects_removed_nodes(tmp_path: Path, operation: str) -> None:
    """Allow collection and reordering, but reject a silently dropped parameter."""
    (tmp_path / "test_example.py").write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('value', [1, 2])\n"
        "def test_example(value):\n"
        "    assert value > 0\n",
        encoding="utf-8",
    )
    (tmp_path / "conftest.py").write_text(
        f"def pytest_collection_modifyitems(items):\n    {operation}\n", encoding="utf-8"
    )
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "tests.collection_audit", "--collect-only", "-q"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTEST_ADDOPTS": "",
            "PYTHONPATH": os.pathsep.join(filter(None, [str(root), os.getenv("PYTHONPATH")])),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    output = result.stdout + result.stderr
    if operation == "items.pop()":
        assert result.returncode == pytest.ExitCode.USAGE_ERROR, output
        assert (
            "Collection hooks removed regressions: ['test_example.py::test_example[2]']" in output
        )
    else:
        assert result.returncode == pytest.ExitCode.OK, output
        assert "test_example.py::test_example[1]" in output
        assert "test_example.py::test_example[2]" in output
