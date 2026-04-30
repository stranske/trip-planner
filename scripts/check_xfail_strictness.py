#!/usr/bin/env python3
"""Acceptance-test xfail strictness ratchet.

Acceptance-style xfails under ``tests/planner/``, ``tests/contracts/``, and
``tests/integrations/`` MUST either set ``strict=True`` (so a passing test
becomes XPASS and surfaces the resolved gap) or carry an explicit
``# xfail-exempt: <reason>`` comment on the same line as the
``@pytest.mark.xfail`` decorator. Unit tests under ``tests/unit/`` are
out of scope.

The script walks each guarded test directory with ``ast``, finds every
``pytest.mark.xfail`` decorator (or alias such as ``mark.xfail`` /
``xfail``), and reports any decorator whose keyword arguments include
``strict=False`` (or omit ``strict=`` entirely) without an exemption marker.
Exit code is non-zero if any violations are found, suitable for wiring into
CI.

Usage::

    python scripts/check_xfail_strictness.py
    python scripts/check_xfail_strictness.py tests/planner tests/contracts

The default guarded directories are the three acceptance lanes named in
``tests/planner/test_planner_turn_acceptance.py`` and recorded in
``tests/planner/MIGRATIONS.md`` (issue #1046).
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

GUARDED_DIRS_DEFAULT = (
    "tests/planner",
    "tests/contracts",
    "tests/integrations",
)
EXEMPTION_MARKER = "xfail-exempt:"


def _iter_python_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*.py")):
        if path.is_file():
            yield path


def _decorator_attribute_chain(node: ast.expr) -> list[str]:
    """Flatten ``pytest.mark.xfail`` / ``mark.xfail`` / ``xfail`` to a name list."""
    chain: list[str] = []
    current: ast.expr | None = node
    while isinstance(current, ast.Attribute):
        chain.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        chain.append(current.id)
    return list(reversed(chain))


def _is_xfail_call(call: ast.Call) -> bool:
    chain = _decorator_attribute_chain(call.func)
    if not chain:
        return False
    return chain[-1] == "xfail" and (
        chain == ["xfail"]
        or chain[-2:] == ["mark", "xfail"]
    )


def _is_strict_true(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg != "strict":
            continue
        value = keyword.value
        if isinstance(value, ast.Constant) and value.value is True:
            return True
    return False


def _line_has_exemption(source_lines: list[str], lineno: int) -> bool:
    if 1 <= lineno <= len(source_lines):
        return EXEMPTION_MARKER in source_lines[lineno - 1]
    return False


def _violations_in_file(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return []
    source_lines = text.splitlines()
    violations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not _is_xfail_call(decorator):
                continue
            if _is_strict_true(decorator):
                continue
            if _line_has_exemption(source_lines, decorator.lineno):
                continue
            violations.append(
                (
                    decorator.lineno,
                    f"@xfail without strict=True on '{node.name}'",
                )
            )
    return violations


def check(directories: Iterable[str], repo_root: Path) -> int:
    rc = 0
    for directory in directories:
        root = repo_root / directory
        for path in _iter_python_files(root):
            for lineno, message in _violations_in_file(path):
                rel = path.relative_to(repo_root)
                print(f"{rel}:{lineno}: {message}", file=sys.stderr)
                rc = 1
    if rc:
        print(
            "\nFix: add `strict=True` to the @pytest.mark.xfail decorator, "
            "or add an `# xfail-exempt: <reason>` comment on the decorator "
            "line documenting why the loose marker is necessary. See "
            "tests/planner/MIGRATIONS.md and issue #1046 for context.",
            file=sys.stderr,
        )
    return rc


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    directories = argv[1:] or list(GUARDED_DIRS_DEFAULT)
    return check(directories, repo_root)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
