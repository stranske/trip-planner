# Issue 1842: saved-verdict handoff after app and database cache restart

This round advances the first task with four HTTP route regressions. A fresh app
instance and database engine recover the authenticated owner, saved trip prices,
and policy verdict from persistent storage. The tests cover compliant and refused
verdicts, both first preparation and retrying an already-prepared handoff.

After resetting the database caches, all policy-service operations are made
unavailable. Preparation still returns a POST form targeting the server-configured
HTTPS portal origin, ignores caller query overrides, and uses the stored traveler
and price facts. Retries preserve the existing preparation timestamp and snapshot
hash. Manager submission and decision remain unknown, and internal source snapshots
remain absent from public metadata.

Verification on 2026-10-11:

- 412 tests passed across `tests/integrations/test_tpp_portal_handoff.py`,
  `tests/app/test_proposal_handoff_schema.py`, `tests/app/test_portal_handoff_flow.py`,
  `tests/app/test_proposal.py`, and `tests/integration/test_saved_portal_handoff.py`,
  using `-m "not slow"`.
- The four new restart cases passed independently.
- Required repository-wide Black check at line length 100 passed: 481 files unchanged.
- Ruff and mypy passed for the changed test file; `git diff --check` passed.

The sandbox's documented asyncio socket-wakeup limitation required a temporary
selector-wait cap under `/tmp/trip_planner_restart_checks`; no repository runtime
code or test assertions were changed for that workaround. Black used one worker.

The first task remains unchecked because native-browser and pinned-producer
verification are unavailable: frontend dependencies and the TPP sibling checkout
are absent. Authenticated receipt/status return and hosted exact-head gates remain
pending; this test does not establish full product acceptance.

Git could not stage the change because this checkout's `.git` is mounted read-only
and cannot create `index.lock`. A separate commit artifact and patch are preserved
under `/tmp/trip-planner-1872-handoff-restart` and
`/tmp/issue-1842-handoff-restart.patch`. GitHub API access also failed, preventing a
PR blocker comment, `needs-human` label, or ready-for-review verification.
