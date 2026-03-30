from __future__ import annotations

from pathlib import Path

from scripts import sync_test_dependencies


def test_find_missing_dependencies_respects_repo_specific_project_modules(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sync_test_dependencies, "PYPROJECT_FILE", tmp_path / "pyproject.toml")
    monkeypatch.setattr(
        sync_test_dependencies, "LOCAL_MODULES_FILE", tmp_path / ".project_modules.txt"
    )

    Path("pyproject.toml").write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[project.optional-dependencies]
dev = [
    "pytest==9.0.2",
]
""".strip(),
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests" / "preferences"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_sample.py").write_text(
        """
from .fixture_corpus import load_fixture_corpus
from ..preferences.fixture_corpus import load_fixture_map
""".strip(),
        encoding="utf-8",
    )

    assert sync_test_dependencies.find_missing_dependencies() == {"fixture_corpus", "preferences"}

    Path(".project_modules.txt").write_text("fixture_corpus\npreferences\n", encoding="utf-8")

    assert sync_test_dependencies.find_missing_dependencies() == set()
