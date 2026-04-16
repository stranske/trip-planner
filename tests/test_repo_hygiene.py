"""Keep bootstrap/runtime repo hygiene expectations from regressing."""

from __future__ import annotations

from pathlib import Path
import subprocess


def _git_ls_files(pattern: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", pattern],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_root_node_modules_is_not_tracked() -> None:
    tracked = _git_ls_files("node_modules/**")
    assert not tracked, (
        "Root node_modules must stay untracked; install app JS dependencies with "
        "`npm --prefix frontend install` instead."
    )


def test_gitignore_documents_expected_node_modules_layout() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "node_modules/" in gitignore
    assert "!.github/scripts/node_modules/" in gitignore
    assert "!.github/scripts/node_modules/**" in gitignore


def test_readme_documents_local_bootstrap_and_optional_integrations() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    expected_snippets = [
        "python -m venv .venv",
        "npm --prefix frontend install",
        "frontend/node_modules",
        "TRIP_PLANNER_DATABASE_URL",
        "VITE_API_BASE_URL",
        "VITE_GOOGLE_MAPS_EMBED_API_KEY",
        "TPP_BASE_URL",
        "TPP_ACCESS_TOKEN",
        "TPP_OIDC_PROVIDER",
        "They do not prove live Google Maps rendering or remote Travel-Plan-Permission transport",
    ]

    for snippet in expected_snippets:
        assert snippet in readme, f"README.md must document {snippet!r}."
