"""Guard TPP migration renames until a B-1/B-2/B-3 PR decision is recorded."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Iterable

_DECISION_RE = re.compile(r"\b(B-[123])\b")
_CHOICE_HINT_RE = re.compile(
    r"\b(chosen|selected|decision|sub-decision|we picked|pick|target)\b",
    re.IGNORECASE,
)
_TPP_SERVICE_PREFIX = "trip_planner/app/services/"
_TPP_MODEL_PATH = "trip_planner/app/models/tpp.py"


def has_recorded_sub_decision(pr_body: str) -> bool:
    decisions = _extract_checked_decisions(pr_body)
    if len(decisions) == 1:
        return True

    chosen = _extract_chosen_decisions(pr_body)
    if len(chosen) == 1:
        return True

    explicit = _extract_explicit_decisions(pr_body)
    return len(explicit) == 1


def _extract_checked_decisions(pr_body: str) -> set[str]:
    matches: set[str] = set()
    for line in pr_body.splitlines():
        if not re.search(r"^\s*[-*]\s*\[[xX]\]", line):
            continue
        decision_match = _DECISION_RE.search(line)
        if decision_match:
            matches.add(decision_match.group(1))
    return matches


def _extract_explicit_decisions(pr_body: str) -> set[str]:
    matches: set[str] = set()
    for line in pr_body.splitlines():
        lower_line = line.lower()
        if "/" in line and "b-1" in lower_line and "b-2" in lower_line and "b-3" in lower_line:
            continue
        if (
            "or" in lower_line
            and "b-1" in lower_line
            and "b-2" in lower_line
            and "b-3" in lower_line
        ):
            continue
        found = {match.group(1) for match in _DECISION_RE.finditer(line)}
        matches.update(found)
    return matches


def _extract_chosen_decisions(pr_body: str) -> set[str]:
    matches: set[str] = set()
    for line in pr_body.splitlines():
        if not _CHOICE_HINT_RE.search(line):
            continue
        found = {match.group(1) for match in _DECISION_RE.finditer(line)}
        matches.update(found)
    return matches


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


def _git_rev_exists(rev_name: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", rev_name],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _fetch_remote_ref(ref_name: str) -> None:
    subprocess.run(
        [
            "git",
            "fetch",
            "--no-tags",
            "--depth=1",
            "origin",
            f"{ref_name}:refs/remotes/origin/{ref_name}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _remote_ref_exists(ref_name: str) -> bool:
    remote_ref = f"refs/remotes/origin/{ref_name}"
    if not _git_ref_exists(remote_ref):
        _fetch_remote_ref(ref_name)
    return _git_ref_exists(remote_ref)


def _add_remote_diff_ranges(candidates: list[str], ref_name: str) -> None:
    if _remote_ref_exists(ref_name):
        candidates.extend([f"origin/{ref_name}...HEAD", f"origin/{ref_name}..HEAD"])


def _resolve_diff_ranges() -> list[str]:
    candidates: list[str] = []
    base_ref = os.getenv("GITHUB_BASE_REF", "").strip()
    if base_ref:
        _add_remote_diff_ranges(candidates, base_ref)

    _add_remote_diff_ranges(candidates, "main")

    if _git_ref_exists("refs/heads/main"):
        candidates.extend(["main...HEAD", "main..HEAD"])

    if _git_rev_exists("HEAD~1"):
        candidates.append("HEAD~1..HEAD")

    return list(dict.fromkeys(candidates))


def _collect_rename_diff_output() -> str:
    errors: list[str] = []
    diff_ranges = _resolve_diff_ranges()
    if not diff_ranges:
        return ""

    for diff_range in diff_ranges:
        try:
            return _run_git(
                ["diff", "--name-status", "--find-renames", "--diff-filter=R", diff_range]
            )
        except (subprocess.CalledProcessError, OSError, ValueError) as exc:
            errors.append(f"{diff_range}: {exc}")

    raise RuntimeError("; ".join(errors))


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


def _is_pr_context() -> bool:
    event_name = os.getenv("GITHUB_EVENT_NAME", "").strip().lower()
    if event_name in {"pull_request", "pull_request_target"}:
        return True
    return bool(os.getenv("GITHUB_BASE_REF", "").strip())


def enforce_guard() -> tuple[bool, str]:
    try:
        diff_output = _collect_rename_diff_output()
    except (subprocess.CalledProcessError, OSError, RuntimeError, ValueError) as exc:
        return False, f"Unable to evaluate git renames for the TPP migration guard: {exc}"

    rename_records = parse_rename_records(diff_output)
    blocked_moves = find_blocked_tpp_moves(rename_records)
    if not blocked_moves:
        return True, "No guarded TPP rename moves detected."

    if not _is_pr_context():
        return True, "Skipping TPP rename guard outside PR context."

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
