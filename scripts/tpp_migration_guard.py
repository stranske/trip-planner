"""Guard TPP migration renames until a B-1/B-2/B-3 PR decision is recorded."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Iterable

_DECISION_RE = re.compile(r"\bB-[123]\b")
_TPP_SERVICE_PREFIX = "trip_planner/app/services/"
_TPP_MODEL_PATH = "trip_planner/app/models/tpp.py"


def has_recorded_sub_decision(pr_body: str) -> bool:
    return bool(_DECISION_RE.search(pr_body))


def parse_rename_records(diff_output: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for line in diff_output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        status, old_path, new_path = parts[0], parts[1], parts[2]
        if not status.startswith("R"):
            continue
        records.append((old_path, new_path))
    return records


def is_tpp_migration_move(old_path: str, new_path: str) -> bool:
    if old_path == _TPP_MODEL_PATH:
        return True
    if old_path.startswith(_TPP_SERVICE_PREFIX) and "tpp" in Path(old_path).name.lower():
        return True
    return False


def find_blocked_tpp_moves(rename_records: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    return [
        (old_path, new_path)
        for old_path, new_path in rename_records
        if is_tpp_migration_move(old_path, new_path)
    ]


def _run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout


def _git_ref_exists(ref_name: str) -> bool:
    result = subprocess.run(["git", "show-ref", "--verify", "--quiet", ref_name], check=False)
    return result.returncode == 0


def _resolve_diff_range() -> str:
    base_ref = os.getenv("GITHUB_BASE_REF", "").strip()
    if base_ref and _git_ref_exists(f"refs/remotes/origin/{base_ref}"):
        return f"origin/{base_ref}...HEAD"

    if _git_ref_exists("refs/remotes/origin/main"):
        return "origin/main...HEAD"

    if _git_ref_exists("refs/heads/main"):
        return "main...HEAD"

    return "HEAD~1..HEAD"


def _read_pr_body_from_event() -> str:
    event_path = os.getenv("GITHUB_EVENT_PATH", "").strip()
    if not event_path:
        return ""

    path = Path(event_path)
    if not path.exists():
        return ""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""

    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict):
        return ""

    body = pull_request.get("body", "")
    return body if isinstance(body, str) else ""


def load_pr_body() -> str:
    return os.getenv("PR_BODY", "") or _read_pr_body_from_event()


def enforce_guard() -> tuple[bool, str]:
    try:
        diff_range = _resolve_diff_range()
        diff_output = _run_git(
            ["diff", "--name-status", "--find-renames", "--diff-filter=R", diff_range]
        )
    except (subprocess.CalledProcessError, OSError, ValueError) as exc:
        return False, f"Unable to evaluate git renames for the TPP migration guard: {exc}"

    rename_records = parse_rename_records(diff_output)
    blocked_moves = find_blocked_tpp_moves(rename_records)
    if not blocked_moves:
        return True, "No guarded TPP rename moves detected."

    pr_body = load_pr_body()
    if not pr_body:
        return (
            False,
            "Detected TPP rename moves but could not read PR body. Record sub-decision B-1/B-2/B-3 in PR body before git mv.",
        )

    if has_recorded_sub_decision(pr_body):
        return True, "TPP rename guard satisfied: PR body records B-1/B-2/B-3 decision."

    formatted_moves = "\n".join(
        f"- {old_path} -> {new_path}" for old_path, new_path in blocked_moves
    )
    return (
        False,
        "Detected TPP rename moves before recording sub-decision B-1/B-2/B-3 in PR body:\n"
        f"{formatted_moves}",
    )


def main() -> int:
    ok, message = enforce_guard()
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
