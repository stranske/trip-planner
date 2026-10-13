# Issue 1842: reject browser-invalid DEL in handoff origins

The first unchecked task's fixed-origin browser POST handoff accepted an ASCII DEL
character in the configured hostname. Python's URL parser accepted that destination,
while Node's browser-compatible URL parser rejected it. Preparation could therefore
persist `prepared` state for an unusable native form action.

The origin preflight now rejects DEL before parsing. Regressions cover both
`TPP_PORTAL_BASE_URL` and its `TPP_BASE_URL` fallback in local, test and production
environments. Route tests confirm invalid configuration returns 503 without changing
the saved proposal, and correcting configuration permits a retry with the same saved
verdict and snapshot hash. Manager submission and decision remain unknown.

Validation on 2026-10-11:

- Before the fix, 12 new hostname regression cases failed because no error was raised.
- `pytest tests/app/test_portal_handoff_flow.py tests/app/test_proposal.py
  tests/app/test_proposal_handoff_schema.py tests/integration/test_saved_portal_handoff.py
  tests/integrations/test_tpp_portal_handoff.py -q -m 'not slow'`: 244 passed.
- Relevant-file Black formatting and the required full repository Black check at line
  length 100 passed; 481 files were unchanged. `git diff --check` passed.

Checks used `/tmp/trip_planner_handoff_checks/sitecustomize.py` to cap selector waits
at 10 milliseconds because this sandbox blocks asyncio socketpair wakeups, and
`BLACK_NUM_WORKERS=1`. This temporary runner workaround is outside the repository;
product code and test assertions were exercised unchanged.

Remaining verification: `npm ci --offline --ignore-scripts --no-audit --no-fund` failed
because the cache lacks `xmlchars-2.2.0.tgz`, so frontend checks could not run. The pinned
TPP sibling checkout is absent. No full task checkbox or product acceptance is claimed.

Delivery blockers: local `git add` failed because `.git` is read-only. The GitHub
connector rejected creating a tree for the three verified Python files because the
call requires approval and this run's approval policy is `never`. The source patch is
saved at `/tmp/trip-planner-1872-handoff-del.patch`. PR #1872 was verified open and
ready for review (`draft=false`) through the GitHub connector before that attempt.
The connector also rejected the requested `needs-human` label and blocker comment
for the same approval requirement. A final read confirmed the PR remains open,
ready for review, and at its original head; no remote changes were made.
