"""Measure function size and cyclomatic complexity for changed product code.

The guard intentionally evaluates only functions that overlap the pull-request
diff. Existing debt stays visible in the report without blocking unrelated
maintenance; a changed function may not exceed the recorded complexity ceiling.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path

_DECISION_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.IfExp,
)


@dataclass(frozen=True, slots=True)
class FunctionMetric:
    path: Path
    name: str
    start_line: int
    end_line: int
    complexity: int


def _nodes_in_function_scope(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.AST]:
    pending: list[ast.AST] = list(node.body)
    nodes: list[ast.AST] = []
    nested_scopes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    while pending:
        child = pending.pop()
        if isinstance(child, nested_scopes):
            continue
        nodes.append(child)
        pending.extend(ast.iter_child_nodes(child))
    return nodes


def _complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    decisions = 1
    for child in _nodes_in_function_scope(node):
        if isinstance(child, _DECISION_NODES):
            decisions += 1
        elif isinstance(child, ast.BoolOp):
            decisions += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            decisions += 1 + len(child.ifs)
        elif isinstance(child, ast.Match):
            decisions += max(0, len(child.cases) - 1)
    return decisions


def measure_file(path: Path) -> list[FunctionMetric]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    metrics: list[FunctionMetric] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            metrics.append(
                FunctionMetric(
                    path=path,
                    name=node.name,
                    start_line=node.lineno,
                    end_line=node.end_lineno if node.end_lineno is not None else node.lineno,
                    complexity=_complexity(node),
                )
            )
    return sorted(
        metrics, key=lambda metric: (metric.path, metric.start_line, metric.name)
    )


def changed_line_ranges(diff: str) -> dict[Path, list[range]]:
    """Return new-file line ranges from a ``git diff --unified=0`` payload."""

    result: dict[Path, list[range]] = {}
    current_path: Path | None = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current_path = Path(line.removeprefix("+++ b/"))
            continue
        if not line.startswith("@@ ") or current_path is None:
            continue
        new_span = line.split(" +", maxsplit=1)[1].split(" ", maxsplit=1)[0]
        start_and_count = new_span.removeprefix("+").split(",", maxsplit=1)
        start = int(start_and_count[0])
        count = int(start_and_count[1]) if len(start_and_count) == 2 else 1
        if count:
            result.setdefault(current_path, []).append(range(start, start + count))
    return result


def changed_functions(
    metrics: list[FunctionMetric], ranges: list[range]
) -> list[FunctionMetric]:
    return [
        metric
        for metric in metrics
        if any(
            metric.start_line < changed_range.stop
            and changed_range.start <= metric.end_line
            for changed_range in ranges
        )
    ]


def _git_diff(base_ref: str, root: Path) -> str:
    return subprocess.run(
        ["git", "diff", "--unified=0", f"{base_ref}...HEAD", "--", str(root)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("trip_planner"))
    parser.add_argument(
        "--changed-from", help="Git ref used to limit enforcement to changed functions"
    )
    parser.add_argument("--max-complexity", type=int, default=25)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    source_files = sorted(args.root.rglob("*.py"))
    all_metrics = [metric for path in source_files for metric in measure_file(path)]

    if not args.changed_from:
        for metric in all_metrics:
            print(
                f"{metric.path}:{metric.start_line}-{metric.end_line} "
                f"{metric.name} complexity={metric.complexity}"
            )
        return 0

    ranges_by_path = changed_line_ranges(_git_diff(args.changed_from, args.root))
    guarded = [
        metric
        for metric in all_metrics
        if metric.path in ranges_by_path
        for metric in changed_functions([metric], ranges_by_path[metric.path])
    ]
    violations = [
        metric for metric in guarded if metric.complexity > args.max_complexity
    ]
    if violations:
        for metric in violations:
            print(
                f"ERROR: {metric.path}:{metric.start_line} {metric.name} has complexity "
                f"{metric.complexity}; the changed-function ceiling is {args.max_complexity}.",
            )
        return 1

    for metric in guarded:
        print(
            f"{metric.path}:{metric.start_line}-{metric.end_line} "
            f"{metric.name} complexity={metric.complexity}",
        )

    print(
        f"Changed-function complexity guard passed: {len(guarded)} function(s) at or below "
        f"{args.max_complexity}.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
