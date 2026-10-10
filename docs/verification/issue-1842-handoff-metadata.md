# Issue 1842: public handoff metadata verification

This round strengthens the first task's server-owned handoff response. The response schema
now exposes only preparation metadata, validates the snapshot hash and schema version,
and requires manager submission and decision to remain unknown. Internal source snapshots
are filtered even if the service returns persisted metadata directly.

Verified acceptance criterion:

- [x] internal source snapshots remain server-side; public payloads expose only status
  metadata and a hash

The outgoing form still contains the server-mapped traveler fields needed by TPP. The
internal proposal, full policy result and source snapshot are excluded from its metadata.

Validation on 2026-10-10:

- 194 tests passed across `tests/app/test_proposal.py`,
  `tests/app/test_portal_handoff_flow.py`, `tests/app/test_proposal_handoff_schema.py`,
  `tests/integration/test_saved_portal_handoff.py` and
  `tests/integrations/test_tpp_portal_handoff.py`, using `-m "not slow"`.
- The endpoint regression verifies filtering against actual persisted source metadata.
- Schema regressions reject invented delivery/decision states and invalid hash/version data.
- Black's full repository check at line length 100 passed: 476 files unchanged.

The sandbox blocks socketpair writes used to wake asyncio loops. Checks used a temporary
`sitecustomize.py` under `/tmp/trip_planner_sandbox_checks` that caps selector waits at
10 milliseconds, plus `BLACK_NUM_WORKERS=1`. This runner workaround changes neither
repository code nor tests.

Remaining verification: frontend tests could not run because the offline npm cache lacks
`xmlchars-2.2.0.tgz`; the real cross-repo contract could not run because the pinned TPP
checkout is absent. These checks remain unverified. GitHub API access also failed, so the
PR checklist and ready-for-review state could not be updated or confirmed from this run.

Commit blocker: `git add` and `git commit` failed because `.git` is mounted read-only and
Git cannot create `index.lock`. The changes remain in the working tree. Applying a
`needs-human` label or posting the blocker to the PR also requires working GitHub API access.
