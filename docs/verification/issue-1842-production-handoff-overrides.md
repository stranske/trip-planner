# Issue 1842: production handoff caller overrides

This round advances the first task with eight regressions through the production
submit/refresh path, without enabling client-supplied evaluation fixtures. Both compliant
and non-compliant saved policy results reject caller-supplied destinations, form fields,
methods, and delivery/decision state. Rejection leaves the persisted verdict and handoff
metadata unchanged; a subsequent empty request prepares the server-owned HTTPS POST.
Preparing the handoff never calls the policy API again.

Verified acceptance criterion:

- [x] the client cannot choose the TPP destination or supply handoff fields

Validation on 2026-10-10:

- 212 tests passed across `tests/app/test_portal_handoff_flow.py`,
  `tests/app/test_proposal.py`, `tests/app/test_proposal_handoff_schema.py`,
  `tests/integration/test_saved_portal_handoff.py`, and
  `tests/integrations/test_tpp_portal_handoff.py`, with `-m "not slow"`.
- The required full repository Black check at line length 100 passed: 478 files unchanged.
- Ruff and `git diff --check` passed.

The sandbox's asyncio wake-up limitation required a temporary selector timeout cap under
`/tmp/trip_planner_sandbox_checks`. Black used a single thread in place of its process
pool. These runner accommodations change neither repository code nor test assertions.

The frontend and real pinned TPP checkout were not rerun in this test-only round, so the
entire browser handoff task is not newly marked complete. Authenticated correlated status
return remains dependent on the accepted producer contract; these tests establish only
preparation, with manager submission and decision unknown.

The repository commit failed because `.git` is read-only. GitHub API access also failed,
preventing a PR checklist update, blocker comment/label, and readiness verification.
