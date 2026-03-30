from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_check_test_dependencies_script_uses_declared_project_dependencies(
    tmp_path: Path,
) -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_test_dependencies.sh"
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[project.optional-dependencies]
dev = [
    "ruff==0.15.1",
    "mypy==1.19.1",
    "pytest==9.0.2",
    "pytest-cov==7.0.0",
    "black==26.1.0",
]
""".strip(),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(script_path)],
        cwd=tmp_path,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "hypothesis" not in result.stdout
    assert "pandas" not in result.stdout
    assert "numpy" not in result.stdout
