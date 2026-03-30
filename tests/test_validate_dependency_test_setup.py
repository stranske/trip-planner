from __future__ import annotations

from pathlib import Path

from scripts import validate_dependency_test_setup


def test_check_lock_file_completeness_uses_requirements_lock(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[project.optional-dependencies]
dev = [
    "ruff==0.15.1",
    "pytest-cov==7.0.0",
]
""".strip(),
        encoding="utf-8",
    )
    Path("requirements.lock").write_text(
        """
ruff==0.15.1
pytest_cov==7.0.0
""".strip(),
        encoding="utf-8",
    )

    passed, issues = validate_dependency_test_setup.check_lock_file_completeness()

    assert passed is True
    assert issues == []


def test_check_for_hardcoded_versions_ignores_domain_numeric_assertions(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_values.py").write_text(
        """
def test_domain_values() -> None:
    assert score == 0.98


def test_version_string() -> None:
    assert package_version == "1.2.3"
""".strip(),
        encoding="utf-8",
    )

    passed, issues = validate_dependency_test_setup.check_for_hardcoded_versions()

    assert passed is False
    assert issues == [
        "Found potential hardcoded versions in tests:",
        '  tests/test_values.py:6: assert package_version == "1.2.3"',
    ]
