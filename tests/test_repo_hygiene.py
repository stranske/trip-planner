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
