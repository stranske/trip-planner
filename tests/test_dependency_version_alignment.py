"""Ensure the lock file captures every dependency declared in pyproject.toml."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import tomllib

_OPERATORS = ("==", ">=", "<=", "~=", "!=", ">", "<", "===")


def _split_spec(raw: str) -> str:
    entry = raw.strip().strip(",").strip('"')
    for operator in _OPERATORS:
        if operator in entry:
            name, _ = entry.split(operator, 1)
            return name.strip().split("[")[0]
    return entry.strip().split("[")[0]


def _load_lock_versions(path: Path) -> Dict[str, str]:
    versions: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("--"):
            continue
        if "==" not in stripped:
            continue
        name, version = stripped.split("==", 1)
        versions[name.lower()] = version
    return versions


def test_all_pyproject_dependencies_are_in_lock() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project", {})

    declared = set()
    for entry in project.get("dependencies", []):
        declared.add(_split_spec(entry).lower())

    for group in project.get("optional-dependencies", {}).values():
        for entry in group:
            declared.add(_split_spec(entry).lower())

    lock_versions = _load_lock_versions(Path("requirements.lock"))

    missing = []
    for dependency in sorted(declared):
        normalised = dependency.replace("-", "_")
        if dependency not in lock_versions and normalised not in lock_versions:
            missing.append(dependency)

    assert (
        not missing
    ), "requirements.lock is missing pinned versions for: " + ", ".join(missing)
