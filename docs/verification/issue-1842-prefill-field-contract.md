# Issue 1842: validate the outgoing prefill field contract

The first task's response schema accepted arbitrary native-form field names. Four
schema regressions and eight route regressions failed on the original code: an
internal source snapshot or unsupported return URL produced a successful response.
The schema now accepts only the 15 fields mapped by the existing server prefill
builder. Invalid mappings fail before persisting preparation, preserve eligible or
prepared state, omit private values from responses and logs, and allow a retry.
A positive check preserves the complete real mapper output, including flight facts.

Validation on 2026-10-11:

- 331 focused tests passed across the proposal route, portal handoff flow, handoff
  schema, portal mapper and saved-verdict integration tests, using `-m "not slow"`.
- The final schema suite passed all 11 cases after adding the complete-mapper check.
- The required repository-wide Black check at line length 100 passed (481 files).
- Changed-file Ruff and Mypy passed; `git diff --check` passed.
- Route tests used the existing documented temporary selector-wait cap under
  `/tmp/trip_planner_handoff_checks`; repository code and assertions were unchanged.

No browser or cross-repo task is marked complete by these backend checks. The local
pinned producer checkout and frontend dependency tree are absent. Full receipt
integration and exact-head hosted checks remain required. Read-only GitHub checks
confirmed PR1872 is open and ready for review at `ebb9b9e2`.

Producer PR1659 is merged at `3010e3e39eb0ae039a1e648f957d8e87441d8e2a`.
Its accepted `docs/contracts/portal-receipt-v1.md` requires complete portal answers
and trusted forwarding of the authenticated traveler's identity; shared service
authentication cannot establish traveler ownership. This iteration does not connect
that contract or infer a delivery receipt or manager decision.

The shared repository's `.git` mount rejects staging with a read-only filesystem
error. A source commit, patch and bundle are preserved in a writable checkout under
`/tmp/trip-planner-1872-prefill-contract` for the owning automation to apply.
