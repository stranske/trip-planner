"""Print a ledger reconciliation patch from verified #2006 run evidence.

This consumer-specific evidence tool never writes the ledger. Review its stdout
before applying it in a checkout where .agents is writable. It deliberately
leaves the combined smoke/local-command task blocked until broad validation
succeeds; a passing historical smoke job cannot establish local test success.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import yaml

INSTALL = '.venv/bin/python -m pip install -e ".[dev]" -e "../trip-planner[dev]"'
RUN = 42484305260
BLOCK = re.compile(r"^  - id: task-\d+\n.*?(?=^  - id: |\Z)", re.MULTILINE | re.DOTALL)


def reconciliation(ledger: str, evidence: dict) -> str:
    """Correct superseded blockers only when receipts establish the merged head."""
    pr = evidence["pull_request"]
    lookup = evidence["run_lookup"]
    head = pr["head_sha"]
    if pr["number"] != 2006 or pr["merged"] is not True:
        raise ValueError("Expected merged PR #2006")
    if not re.fullmatch(r"[0-9a-f]{40}", head) or lookup["commit_sha"] != head:
        raise ValueError("Run lookup must use #2006's final head")
    runs = [run for run in lookup["workflow_runs"] if run["id"] == RUN]
    if len(runs) != 1 or (runs[0]["status"], runs[0]["conclusion"]) != ("completed", "success"):
        raise ValueError("Successful run 42484305260 is required at the final head")
    jobs = [job for job in evidence["jobs"] if job["name"] == "cross-repo-full-product"]
    if (
        len(jobs) != 1
        or jobs[0]["run_id"] != RUN
        or (jobs[0]["status"], jobs[0]["conclusion"]) != ("completed", "success")
    ):
        raise ValueError("Smoke job must pass in run 42484305260")
    failed = "\n".join(evidence["log_excerpts"]["42449207754"])
    passed = "\n".join(evidence["log_excerpts"][str(RUN)])
    if not all(INSTALL in log for log in (failed, passed)):
        raise ValueError("Both logs must establish the local editable install inputs")
    if (
        "TPP_PINNED_REF: acc4aeddee5f4ffefbdc73fcb07505cd3d198197" not in failed
        or "TPP_PINNED_REF: b56d92b389736c70370aa9134f379ac8cd1f3ad1" not in passed
    ):
        raise ValueError("Both logs must identify the actual pinned TPP checkouts")
    if not all(
        value in failed for value in ("ResolutionImpossible", "ruff==0.17.2", "ruff==0.17.3")
    ):
        raise ValueError("Historical log must establish the conflicting Ruff metadata")
    if f"Merge {head} into " not in passed:
        raise ValueError("Successful checkout must contain the final PR head")
    if not all(value in passed for value in ("Successfully installed", "ruff-0.17.3")):
        raise ValueError("Successful log must establish the resolved installation")

    # Historical notes elsewhere contain unquoted colons and are invalid YAML.
    # Do not reinterpret or rewrite them while correcting these two entries.
    if not re.search(r"^issue: 2007$", ledger, re.MULTILINE):
        raise ValueError("Expected issue-2007 ledger")
    blocks = BLOCK.findall(ledger)
    for task_id in ("task-05", "task-14"):
        if sum(block.startswith(f"  - id: {task_id}\n") for block in blocks) != 1:
            raise ValueError(f"Expected exactly one {task_id}")

    receipt = f"{evidence['checked_at']}: PR #2006 merged {pr['merged_at']}; final head {head}."
    notes = {
        "task-05": [
            receipt,
            f"Both run logs install local editable dev extras: {INSTALL}",
            "Historical run 42449207754 fails on Ruff 0.17.2 versus 0.17.3. "
            "Run 42484305260 installs compatible checkouts successfully.",
            "The source-pin edit and PyPI republication proposal are superseded. "
            "This also corrects task-03's PyPI diagnosis. No source-pin edit was "
            "performed; defer rather than mark it complete.",
        ],
        "task-14": [
            receipt,
            "Run 42484305260: cross-repo-full-product success at the final PR head. "
            "Regeneration is no longer a blocker.",
            "The documented owning-repository local command still needs a successful "
            "run. Retained owner-dev-check.log exits 1 provisioning missing formatter "
            "tooling; do not infer local test success from historical smoke.",
        ],
    }

    def replace(match: re.Match) -> str:
        task_id = match[0].splitlines()[0].removeprefix("  - id: ")
        if task_id not in notes:
            return match[0]
        prefix, separator, _ = match[0].partition("    notes:\n")
        if not separator:
            raise ValueError("Unsupported ledger notes layout")
        status = "deferred" if task_id == "task-05" else "blocked"
        prefix, count = re.subn(r"^    status: \w+$", f"    status: {status}", prefix, flags=re.M)
        if count != 1:
            raise ValueError("Unsupported ledger status layout")
        rendered = yaml.safe_dump(notes[task_id], width=100).splitlines(keepends=True)
        result = prefix + separator + "".join("      " + line for line in rendered)
        assert yaml.safe_load(result)[0]["notes"] == notes[task_id]
        return result

    return BLOCK.sub(replace, ledger)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=Path(".agents/issue-2007-ledger.yml"))
    parser.add_argument(
        "--evidence", type=Path, default=Path("docs/evidence/issue-2025/run-reconciliation.json")
    )
    args = parser.parse_args()
    try:
        original = args.ledger.read_text(encoding="utf-8")
        updated = reconciliation(original, json.loads(args.evidence.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"Cannot reconcile ledger: {exc}", file=sys.stderr)
        return 1
    sys.stdout.writelines(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{args.ledger.as_posix()}",
            tofile=f"b/{args.ledger.as_posix()}",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
