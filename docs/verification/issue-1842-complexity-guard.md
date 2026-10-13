# Issue 1842: handoff complexity guard recovery

- [x] Reproduce and fix the Complexity guard failure; run its exact command and
  focused regression tests.
- [ ] Integrate authenticated correlated receipt/status return and recorded
  manager decisions from accepted TPP producer issue #1658.

The first checkbox records local implementation verification. The PR head still
requires application of this change and hosted checks before merge.

The exact CI command, `python scripts/measure_complexity.py --changed-from
origin/main --max-complexity 25`, initially failed because `portal_action_url`
had complexity 26. Browser-compatible hostname validation and loopback
classification now live together in `_portal_host_is_loopback`, with complexity
8. `portal_action_url` has complexity 19. The command passes for all 36 changed
functions. Validation order, error messages, fixed form destination and HTTPS
restrictions are preserved; the guard and its ceiling are unchanged.

## Verification on 2026-10-11

- `pytest tests/integrations/test_tpp_portal_handoff.py
  tests/integrations/test_tpp_portal_receipt.py tests/test_measure_complexity.py
  -q -m "not slow"`: 333 passed.
- `pytest tests/integration/test_saved_portal_handoff.py -q -m "not slow"`:
  27 passed.
- `pytest tests/app/test_portal_handoff_flow.py -q -m "not slow"`: 82 passed.
- Changed-file Black, Ruff and Mypy pass; `git diff --check` passes.
- Required repository-wide Black check at line length 100 passes: 481 files
  unchanged.

ASGI tests and repository-wide Black use the previously documented temporary
selector-wait workaround under `/tmp/trip_planner_sandbox_checks`, added to
`PYTHONPATH`. ASGI checks use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; Black uses
`BLACK_NUM_WORKERS=1`. This changes no repository code, assertions or validation
rules.

## Remaining receipt integration

Producer issue #1658 is implemented by merged PR #1659 at
`3010e3e39eb0ae039a1e648f957d8e87441d8e2a`. Its accepted contract requires
complete portal answers and owner-authenticated individual TPP identity. The
consumer currently stores partial prefill and uses its own account session;
neither a correlation ID nor shared service identity authorizes receipt reads.
The established individual identity bridge and source of completed answers must
be provided before connecting that API. Preparation-only scope reduction is not
selected, and the active manager-status review remains unresolved.

The owning high-privilege lane must update the protected producer workflow pin
and run the actual two-app contract after integration. No workflow is changed
in this run. This checkout's `.git` is mounted read-only, preventing staging;
the source change remains in the working tree for owning automation to apply.
