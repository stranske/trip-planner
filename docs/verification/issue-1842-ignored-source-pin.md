# Issue 1842: ignored source in the producer pin

Reviewed commits through `f1f8ccf3`. The original four browser preparation tasks
and four security criteria are implemented. The reconciled PR body is saved at
`/tmp/trip-planner-1872-reconciled-body.md`; GitHub rejected the body update,
`needs-human` label and blocker comment because approval is required and this
run's approval policy is `never`. Remote checkboxes remain unchanged.

The first remaining task is the real pinned producer contract. Its checkout gate
now rejects ignored modules, standalone bytecode, native modules and policy
resources under `src`, which ordinary Git status omits. Normal `__pycache__`
bytecode remains allowed. Optional unpinned local development remains supported.

Verified with Python 3.14.8 and `-m "not slow"`:

- Existing backend handoff/proposal/schema/saved-state and checkout/import batch:
  250 passed.
- Updated checkout/import gate: 33 passed.
- New ignored-source cases against the previous gate, in an isolated copy:
  five failed with the intended missing rejection; two compatibility cases passed.
- Changed-file Ruff and Mypy passed; `git diff --check` passed.
- Required repository-wide Black check at line length 100: 481 files unchanged.

App and Black checks used the temporary selector-wait workaround described in
`issue-1842-handoff-metadata.md`. No repository test was disabled or modified
for that workaround.

The producer clone failed because GitHub DNS is unavailable. Frontend dependencies
are absent. The real two-app gate, hosted checks and full receipt/status integration
remain unverified and unchecked. TPP PR1659 is merged at
`3010e3e39eb0ae039a1e648f957d8e87441d8e2a`; its accepted receipt contract
supersedes the former no-endpoint criterion. Trusted per-traveler identity,
complete answers, authenticated transport, persistence and workspace display
remain necessary. The hosted pin change requires the approved privileged lane;
no protected file was edited here.

The PR was confirmed open and ready for review. Workspace Git staging failed
because `.git` is read-only. A separate checkout under
`/tmp/trip-planner-1872-ignored-source-commit` preserves the source commit;
`/tmp/trip-planner-1872-ignored-source.patch` and
`/tmp/trip-planner-1872-ignored-source.bundle` provide handoff artifacts.
