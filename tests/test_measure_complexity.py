import subprocess
import sys
from pathlib import Path

from scripts.measure_complexity import (
    changed_functions,
    changed_line_ranges,
    measure_file,
)


def test_measure_complexity_counts_boolean_and_branch_decisions(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def guarded(value):\n"
        "    if value and value > 1:\n"
        "        return value\n"
        "    return 0\n",
        encoding="utf-8",
    )

    metric = measure_file(source)[0]

    assert metric.complexity == 3


def test_measure_complexity_excludes_nested_scopes_and_counts_generators(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def guarded(items):\n"
        "    def nested(value):\n"
        "        if value:\n"
        "            return value\n"
        "        return 0\n"
        "    return [item for item in items for _ in range(2) if item]\n",
        encoding="utf-8",
    )

    metric = measure_file(source)[0]

    assert metric.name == "guarded"
    assert metric.complexity == 4


def test_changed_function_guard_selects_only_functions_touched_by_diff(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def unchanged():\n"
        "    return 1\n\n"
        "def changed(value):\n"
        "    if value:\n"
        "        return 1\n"
        "    return 0\n",
        encoding="utf-8",
    )
    diff = "+++ b/sample.py\n@@ -4,0 +5,1 @@\n+    if value:\n"

    selected = changed_functions(
        measure_file(source), changed_line_ranges(diff)[Path("sample.py")]
    )

    assert [metric.name for metric in selected] == ["changed"]


def test_complexity_cli_rejects_a_changed_function_over_the_ceiling(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "trip_planner"
    source_root.mkdir()
    source = source_root / "sample.py"
    source.write_text("def guarded():\n    return 0\n", encoding="utf-8")
    for command in (
        ["git", "init", "--quiet"],
        ["git", "config", "user.email", "tests@example.com"],
        ["git", "config", "user.name", "Complexity tests"],
        ["git", "add", "trip_planner/sample.py"],
        ["git", "commit", "--quiet", "-m", "baseline"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True)

    source.write_text(
        "def guarded(value):\n"
        "    if value == 0:\n        return 0\n"
        "    if value == 1:\n        return 1\n"
        "    if value == 2:\n        return 2\n"
        "    return 3\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "trip_planner/sample.py"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "--quiet", "-m", "deliberate break"], cwd=tmp_path, check=True
    )

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "scripts" / "measure_complexity.py"),
            "--changed-from",
            "HEAD~1",
            "--max-complexity",
            "3",
        ],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert "changed-function ceiling is 3" in result.stdout
