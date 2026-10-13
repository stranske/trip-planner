# Issue 1842: bind policy details beyond the displayed verdict

The first task's full authenticated handoff remains incomplete. The accepted
producer contract at `3010e3e39eb0ae039a1e648f957d8e87441d8e2a` requires complete
portal answers and trusted forwarding of the authenticated traveler's identity.
The existing planner form has partial answers, and receipt validation is not yet
connected to workspace preparation or refresh. This round advances the second
task's saved-result hash verification without reducing the approved product scope.

Twelve new saved-route cases cover eligible and already-prepared handoffs when
the evaluation ID, approval reason, mandatory approval flag, exception guidance,
policy notes or compliance score changes. The headline remains `compliant`, and
the native browser form fields remain identical. Reusing the previous binding
returns 409 and preserves the saved handoff and trip timestamp. Ingesting the
fresh result through the policy service changes the hash, clears preparation,
and permits a newly prepared form. Reloaded public metadata contains no private
snapshot and continues to report unknown manager submission and decision.

A temporary pytest plugin deliberately removed the complete policy result from
the hash input while retaining the headline verdict. All twelve new cases failed
because stale preparation was incorrectly allowed. The mutation was confined to
`/tmp/trip_planner_policy_binding_mutation.py`; repository runtime code was unchanged.

Validation on 2026-10-12:

- Existing baseline: 302 passed across portal mapping, saved handoff and schema tests.
- New regression cases: 12 passed; deliberate mutation: 12 failed as expected.
- `pytest tests/integrations/test_tpp_portal_handoff.py
  tests/integration/test_saved_portal_handoff.py tests/app/test_proposal_handoff_schema.py
  tests/integrations/test_results.py tests/integrations/test_tpp_portal_receipt.py
  -q -m 'not slow'`: 414 passed.
- Changed-file Black at line length 100, Ruff, mypy and `git diff --check` passed.
- Required repository Black check at line length 100 passed: 481 files unchanged.
  Black used one worker and a temporary selector timeout cap under
  `/tmp/trip-planner-policy-binding-checks` for the sandbox's socket wakeup constraint.

No full-product acceptance checkbox is completed. The pinned two-app contract,
authenticated workspace receipt/status integration and hosted checks remain
required. PR1872 was observed open and ready for review at `47b802879d3175a65a4862963dacaffe5951febd`.

The shared `.git` mount is read-only and rejects staging. The source commit is
preserved in `/tmp/trip-planner-policy-detail-binding-commit`, with an apply-ready
patch and bundle under `/tmp/trip-planner-policy-detail-binding`. The owning
writable lane must apply and publish it.
