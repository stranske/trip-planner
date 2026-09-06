"""Exercise the validator's real CLI against isolated repository inputs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/validate_dependency_test_setup.py"


@pytest.fixture
def repo_fixture(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "trip-planner"
dependencies = ["fastapi>=0.100,<1", "ignored==1; python_version < '2'"]
[project.optional-dependencies]
qa-tools = ["PyYAML>=6,<7", "app-baseline-kit @ https://example.test/kit.whl"]
[tool.uv.pip]
no-emit-package = ["app-baseline-kit"]
""",
        encoding="utf-8",
    )
    (tmp_path / "requirements.lock").write_text(
        "# generated lock\nfastapi==0.141.1\n    # via trip-planner\npyyaml==6.0.3\n",
        encoding="utf-8",
    )
    for relative in ("trip_planner/__init__.py", "trip_planner/app/main.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# app package\n", encoding="utf-8")
    return tmp_path


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=root, text=True, capture_output=True, check=False
    )


def test_validator_passes_for_repo_fixture_and_ignores_numeric_product_assertions(
    repo_fixture: Path,
) -> None:
    tests = repo_fixture / "tests"
    tests.mkdir()
    (tests / "test_amount.py").write_text(
        'assert typical_amount == 165.0\nassert ratio == 0.75\nassert version == "1.0"\n',
        encoding="utf-8",
    )
    # A legacy probe would see this decoy and incorrectly demand Trend serialization.
    legacy = repo_fixture / "src/trend_analysis/io/validators.py"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("# unrelated legacy path; no metadata serializer\n", encoding="utf-8")
    result = run_validator(repo_fixture)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "application paths agree" in result.stdout
    assert not (repo_fixture / ".github").exists()


@pytest.mark.parametrize(
    ("lock", "message"),
    [
        ("fastapi==0.141.1\n", "PyYAML: missing"),
        ("fastapi==0.141.1\npyyaml==5.4.1\n", "does not satisfy"),
        ("fastapi>=0.100\npyyaml==6.0.3\n", "exact version"),
        ("fastapi==0.141.1\npyyaml==6.0.3 ; python_version < '2'\n", "PyYAML: missing"),
        ("not a valid requirement!\n", "invalid locked requirement"),
    ],
)
def test_validator_rejects_inconsistent_lock(repo_fixture: Path, lock: str, message: str) -> None:
    (repo_fixture / "requirements.lock").write_text(lock, encoding="utf-8")
    result = run_validator(repo_fixture)
    assert result.returncode == 1
    assert message in result.stdout


@pytest.mark.parametrize("relative", ["trip_planner/app/main.py", "trip_planner/__init__.py"])
def test_validator_requires_real_application_path(repo_fixture: Path, relative: str) -> None:
    (repo_fixture / relative).unlink()
    result = run_validator(repo_fixture)
    assert result.returncode == 1
    assert relative in result.stdout


@pytest.mark.parametrize("filename", ["pyproject.toml", "requirements.lock"])
def test_validator_reports_missing_inputs(repo_fixture: Path, filename: str) -> None:
    (repo_fixture / filename).unlink()
    result = run_validator(repo_fixture)
    assert result.returncode == 1
    assert filename in result.stdout


def test_validator_reports_malformed_project(repo_fixture: Path) -> None:
    (repo_fixture / "pyproject.toml").write_text("[broken", encoding="utf-8")
    result = run_validator(repo_fixture)
    assert result.returncode == 1
    assert "Invalid dependency inputs" in result.stdout


@pytest.mark.parametrize("matches", [True, False])
def test_validator_compares_non_omitted_direct_urls(repo_fixture: Path, matches: bool) -> None:
    project = repo_fixture / "pyproject.toml"
    project.write_text(
        project.read_text(encoding="utf-8").replace(
            'no-emit-package = ["app-baseline-kit"]', "no-emit-package = []"
        ),
        encoding="utf-8",
    )
    url = "https://example.test/kit.whl" if matches else "https://example.test/old.whl"
    with (repo_fixture / "requirements.lock").open("a", encoding="utf-8") as stream:
        stream.write(f"app-baseline-kit @ {url}\n")
    result = run_validator(repo_fixture)
    assert result.returncode == (0 if matches else 1)
    if not matches:
        assert "locked URL differs" in result.stdout


def test_validator_checks_runtime_dependencies(repo_fixture: Path) -> None:
    (repo_fixture / "requirements.lock").write_text("pyyaml==6.0.3\n", encoding="utf-8")
    result = run_validator(repo_fixture)
    assert result.returncode == 1
    assert "runtime: fastapi: missing" in result.stdout


def test_validator_accepts_explicit_prerelease_declaration(repo_fixture: Path) -> None:
    project = repo_fixture / "pyproject.toml"
    project.write_text(
        project.read_text(encoding="utf-8").replace("fastapi>=0.100,<1", "fastapi>=0.142rc1,<1"),
        encoding="utf-8",
    )
    lock = repo_fixture / "requirements.lock"
    lock.write_text(
        lock.read_text(encoding="utf-8").replace("fastapi==0.141.1", "fastapi==0.142rc1"),
        encoding="utf-8",
    )
    result = run_validator(repo_fixture)
    assert result.returncode == 0, result.stdout
