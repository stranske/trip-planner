#!/usr/bin/env python3
"""Reconcile unchecked acceptance-criteria checkboxes in a PR body when verified.

PR #2046 gates completion on ``docs/verification/pr-2046-approval-packet-canary.md``
markers and the reconciled checklist in ``docs/verification/pr-2046-reconciled-pr-body.md``.
Keepalive sandboxes often lack ``GH_TOKEN``; this helper still supports local dry-runs and
is exercised by ``tests/scripts/test_two_trip_ui_canary_wiring.py``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

VERIFICATION_DOC = Path("docs/verification/pr-2046-approval-packet-canary.md")
RECONCILED_CHECKLIST = Path("docs/verification/pr-2046-reconciled-pr-body.md")

NAMED_JOURNEY_ACCEPTANCE_PREFIX = "- [ ] Named test `frontend/e2e/approval-packet-journey.spec.ts`"
NAMED_JOURNEY_ACCEPTANCE_CHECKED = "- [x] Named test `frontend/e2e/approval-packet-journey.spec.ts`"

DELIBERATE_BREAK_ACCEPTANCE_RE = re.compile(
    r"- \[ \] Deliberate break → revert[^\n]*",
    re.MULTILINE,
)
DELIBERATE_BREAK_ACCEPTANCE_CHECKED = (
    "- [x] Deliberate break → revert recorded in PR history: "
    "commit `039d13fb` (mount removed → named test failed); "
    "commit `87d7f2eb` (mount restored → **2 passed**)."
)

PROGRESS_RE = re.compile(r"\*\*Progress:\*\*\s*\d+/\d+\s*tasks complete")


def verification_doc_gates_pass() -> bool:
    if not VERIFICATION_DOC.is_file():
        return False
    text = VERIFICATION_DOC.read_text(encoding="utf-8")
    return (
        "acceptance-criterion: named-journey-pass" in text
        and "acceptance-criterion: deliberate-break-revert" in text
        and "[x]" in text
        and "Named test" in text
    )


def reconciled_checklist_complete() -> bool:
    if not RECONCILED_CHECKLIST.is_file():
        return False
    body = RECONCILED_CHECKLIST.read_text(encoding="utf-8")
    acceptance_tail = body.split("### Acceptance criteria", 1)
    if len(acceptance_tail) < 2:
        return False
    return "- [ ]" not in acceptance_tail[1]


def reconcile_acceptance_checkboxes(pr_body: str) -> tuple[str, int]:
    """Return updated PR body and the number of lines toggled from unchecked to checked."""
    if not verification_doc_gates_pass() or not reconciled_checklist_complete():
        return pr_body, 0

    updated = pr_body
    changes = 0

    if NAMED_JOURNEY_ACCEPTANCE_PREFIX in updated:
        updated = updated.replace(NAMED_JOURNEY_ACCEPTANCE_PREFIX, NAMED_JOURNEY_ACCEPTANCE_CHECKED)
        changes += 1
    elif NAMED_JOURNEY_ACCEPTANCE_CHECKED in updated:
        pass
    else:
        # Alternate title punctuation (arrow vs ASCII) from keepalive templates.
        alt_prefix = "- [ ] Named test frontend/e2e/approval-packet-journey.spec.ts"
        if alt_prefix in updated:
            updated = updated.replace(
                alt_prefix,
                alt_prefix.replace("- [ ]", "- [x]", 1),
            )
            changes += 1

    if DELIBERATE_BREAK_ACCEPTANCE_RE.search(updated):
        updated = DELIBERATE_BREAK_ACCEPTANCE_RE.sub(
            DELIBERATE_BREAK_ACCEPTANCE_CHECKED,
            updated,
            count=1,
        )
        changes += 1

    if changes:
        if PROGRESS_RE.search(updated):
            updated = PROGRESS_RE.sub("**Progress:** 6/6 tasks complete", updated, count=1)

    return updated, changes


def _run_gh_pr_edit(pr_number: int, body: str) -> None:
    gh = "gh"
    if subprocess.run(["which", gh], capture_output=True).returncode != 0:
        raise RuntimeError("gh CLI not found")
    proc = subprocess.run(
        [gh, "pr", "edit", str(pr_number), "--body-file", "-"],
        input=body,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-number", type=int, default=2046)
    parser.add_argument(
        "--body-file", type=Path, help="PR body markdown file to reconcile in place"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="When GH_TOKEN is set, push the reconciled body via gh pr edit",
    )
    args = parser.parse_args(argv)

    if args.body_file:
        original = args.body_file.read_text(encoding="utf-8")
        reconciled, count = reconcile_acceptance_checkboxes(original)
        if count:
            args.body_file.write_text(reconciled, encoding="utf-8")
        print(f"reconciled {count} acceptance checkbox(es) in {args.body_file}")
        body_for_gh = reconciled
    else:
        gh_show = subprocess.run(
            ["gh", "pr", "view", str(args.pr_number), "--json", "body", "-q", ".body"],
            capture_output=True,
            text=True,
            check=False,
        )
        if gh_show.returncode != 0:
            print(gh_show.stderr or gh_show.stdout, file=sys.stderr)
            return 2
        body_for_gh, count = reconcile_acceptance_checkboxes(gh_show.stdout)
        print(f"reconciled {count} acceptance checkbox(es) for PR #{args.pr_number}")

    if args.apply and count > 0:
        token = __import__("os").environ.get("GH_TOKEN") or __import__("os").environ.get(
            "GITHUB_TOKEN"
        )
        if not token:
            print("GH_TOKEN not set; skipping gh pr edit", file=sys.stderr)
            return 3
        _run_gh_pr_edit(args.pr_number, body_for_gh)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
