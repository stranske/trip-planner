# Issue 1842: verdict removal during authenticated handoff preparation

This change advances the first handoff task. If a trip edit clears the saved
proposal while TPP creates the browser review capability, authenticated
preparation now reloads the current proposal and returns HTTP 409. It does not
return or persist a browser capability for the deleted verdict. A replaced
proposal is also rejected before the original preparation can be committed.

The regression uses the production `update_trip` service in a separate
transaction during browser-session creation. It checks that the edit survives,
the proposal remains absent, and retrying does not create another producer
preparation or browser session.

Validation on 2026-10-12:

- The new regression fails against the original implementation with
  `sqlalchemy.orm.exc.ObjectDeletedError`; it passes with the fix.
- The existing price-edit and proposal-revision race regressions also pass.
- 606 focused tests passed with `-m "not slow"` across
  `tests/integration/test_workspace_portal_preparation.py`,
  `tests/integration/test_workspace_portal_receipt.py`,
  `tests/integration/test_saved_portal_handoff.py`,
  `tests/integrations/test_tpp_portal_handoff.py`,
  `tests/integrations/test_tpp_portal_receipt.py`,
  `tests/integrations/test_tpp_portal_receipt_client.py`,
  `tests/app/test_portal_handoff_request.py`, and
  `tests/app/test_proposal_handoff_schema.py`.
- `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`
  passed: 488 files unchanged. Ruff on both changed Python files and
  `git diff --check` passed.

Black and the combined suite used `BLACK_NUM_WORKERS=1` where applicable and a
temporary selector timeout cap in
`/tmp/trip-planner-handoff-validation/sitecustomize.py`, because the sandbox
blocks asyncio socket wakeups. Application code and test assertions were not
altered by that workaround.

The optional pinned TPP checkout is unavailable in this run. Offline frontend
installation lacks `xmlchars-2.2.0.tgz`, so browser tests remain unverified.
This consumer regression does not establish real producer acceptance. No task
checkbox is marked complete; pinned producer integration, browser acceptance,
and hosted exact-head checks remain required.

The checkout's `.git` directory is read-only. The tested source changes are
retained in the workspace and committed in an isolated repository under
`/tmp/trip-planner-handoff-race/commit`; the patch and bundle are in its parent
directory. The PR branch is not pushed by this run. PR #1872 was observed open
and ready for review.
