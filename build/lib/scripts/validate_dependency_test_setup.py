#!/usr/bin/env python3
"""Validate Trip Planner's declared dependencies against its pip-format lock.

Run from the repository root after installing the development dependencies.
Checks apply to the current interpreter/platform and every optional group.
Explicit tool.uv.pip.no-emit-package entries are intentionally absent from the
lock. Product test literals and centrally managed workflows are not inputs.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def _applies(requirement: Requirement, extra: str = "") -> bool:
    return requirement.marker is None or requirement.marker.evaluate({"extra": extra})


def _locked_requirements(path: Path) -> dict[str, list[Requirement]]:
    locked: dict[str, list[Requirement]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            requirement = Requirement(line)
        except ValueError as exc:
            raise ValueError(f"{path}:{number}: invalid locked requirement: {exc}") from exc
        if _applies(requirement):
            locked.setdefault(canonicalize_name(requirement.name), []).append(requirement)
    return locked


def _check_requirement(requirement: Requirement, locked: list[Requirement]) -> str | None:
    if not locked:
        return f"{requirement.name}: missing from requirements.lock"
    for pin in locked:
        if requirement.url:
            if pin.url != requirement.url:
                return f"{requirement.name}: locked URL differs from declaration"
            continue
        versions = list(pin.specifier)
        if (
            pin.url
            or len(versions) != 1
            or versions[0].operator != "=="
            or "*" in versions[0].version
        ):
            return f"{requirement.name}: lock entry must specify an exact version"
        version = versions[0].version
        if not requirement.specifier.contains(version):
            return f"{requirement.name}: locked {version} does not satisfy {requirement.specifier}"
    return None


def validate(root: Path) -> list[str]:
    """Return declaration, lock, and application-package contract failures."""
    try:
        with (root / "pyproject.toml").open("rb") as stream:
            config = tomllib.load(stream)
        locked = _locked_requirements(root / "requirements.lock")
        project = config["project"]
        groups = {"": project.get("dependencies", []), **project.get("optional-dependencies", {})}
        omitted = {
            canonicalize_name(name)
            for name in config.get("tool", {})
            .get("uv", {})
            .get("pip", {})
            .get("no-emit-package", [])
        }
        issues = []
        for extra, declarations in groups.items():
            for declaration in declarations:
                requirement = Requirement(declaration)
                name = canonicalize_name(requirement.name)
                if not _applies(requirement, extra) or name in omitted:
                    continue
                issue = _check_requirement(requirement, locked.get(name, []))
                if issue:
                    issues.append(f"{extra or 'runtime'}: {issue}")
        # This is the package serving the documented planner application.
        for relative in ("trip_planner/__init__.py", "trip_planner/app/main.py"):
            if not (root / relative).is_file():
                issues.append(f"Missing Trip Planner application path: {relative}")
        return issues
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"Invalid dependency inputs: {exc}"]


def main() -> int:
    """Print actionable diagnostics and return a shell-friendly exit status."""
    issues = validate(Path.cwd())
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Trip Planner dependency declarations, lock metadata, and application paths agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
