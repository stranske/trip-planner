# Issue 1842: consumer receipt validation

The browser preparation tasks are implemented, but the owner-authorized receipt
and manager decision return remains incomplete. Reviewed commits through
`ed27ef48`; the proposed reconciled PR body is saved at
`/tmp/trip-planner-1872-reconciled-body.md`. The connector rejected the body update,
`needs-human` label and blocker comment because mutations require approval and
this run's approval policy is `never`. No remote checkbox changed.

TPP receipt PR1659 merged at `3010e3e39eb0ae039a1e648f957d8e87441d8e2a`.
Its `docs/contracts/portal-receipt-v1.md` supersedes the no-endpoint criterion.
The consumer now validates that response contract: immutable handoff/version/
draft/answer-hash correlation, explicit submission and review evidence, actual
decision values and timestamps, and metadata-only responses. Malformed or
mismatched observations raise a generic contract error without exposing inputs.
The producer's normalized answer digest is distinct from the saved planner
source snapshot hash.

This parser grants no authentication authority and is not yet connected to a
workspace route. The consumer still needs trusted traveler identity forwarding,
complete immutable portal answers, authenticated transport, receipt persistence
and workspace display, unavailable/stale handling, and a real two-app test.
Current browser preparation continues to report unknown submission and decision.
The hosted smoke pin still predates receipts. Updating the protected workflow
requires the owning approved privileged lane; no workflow was edited here.

Verified on 2026-10-10 with Python 3.14.8:

- Existing focused backend/checkout baseline: 158 passed.
- New `tests/integrations/test_tpp_portal_receipt.py`: 50 passed.
- Combined receipt, handoff, validation, proposal and checkout regressions:
  287 passed, using `-m "not slow"`.
- Changed-file Ruff and receipt-module Mypy passed.
- `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`:
  passed, 480 files unchanged. Whitespace check passed.

The sandbox checks used the temporary selector-wait workaround already documented
in `issue-1842-handoff-metadata.md`, outside the repository. The real pinned TPP
checkout and frontend dependencies are absent; no fresh two-app, frontend or
hosted acceptance is claimed. Shared-checkout staging fails because `.git` is
read-only. An isolated checkout under `/tmp/trip-planner-1872-receipt-commit`
preserves the source commit; a bundle and patch are provided for the owning lane.
