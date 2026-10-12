# Issue 1842: reject ports that cannot receive a browser handoff

The first unchecked task's fixed-origin handoff accepted HTTPS origins on ports
that native browser form navigation blocks, including `0`, `25` and `6000`.
The server could therefore persist `prepared` even though the browser could not
deliver its POST. The new regression failed before the implementation change.

The origin validator now rejects the ports in the
[Fetch Standard's bad-port table](https://fetch.spec.whatwg.org/#port-blocking)
before preparation is persisted. This also applies to local HTTP loopback
origins. Allowed custom ports remain supported. Saved-state regressions cover
both configured URL settings, first preparation and retries, and IPv6. A rejected
configuration preserves the saved verdict, handoff metadata and trip timestamp;
correcting the origin allows preparation without another policy check.

## Verification on 2026-10-12

- `pytest tests/integrations/test_tpp_portal_handoff.py
  tests/app/test_proposal_handoff_schema.py
  tests/integration/test_saved_portal_handoff.py -q -m "not slow"`: 363 passed.
- `pytest tests/app/test_portal_handoff_flow.py tests/app/test_proposal.py
  -q -m "not slow"`: 176 passed.
- Changed-file Black and Ruff, module Mypy and `git diff --check` pass.
- `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`:
  481 files unchanged.
- `python scripts/measure_complexity.py --changed-from origin/main
  --max-complexity 25`: passes; `portal_action_url` has complexity 20.

Black and ASGI tests used the previously documented temporary selector-wait cap
under `/tmp/trip-planner-1872-browser-ports-checks`. Black used
`BLACK_NUM_WORKERS=1`; ASGI tests used `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
Repository tests, assertions and validation rules were unchanged by the workaround.

## Handoff and remaining verification

No parent task or acceptance criterion is marked complete by this focused change.
Frontend dependencies and the pinned TPP checkout are absent, so actual browser
and two-app checks remain unverified. The authenticated receipt/status integration
requirement remains in scope; this change does not reduce it to preparation only.

The workspace's `.git` is read-only: staging fails when creating `index.lock`.
The source commit is preserved in a writable Git repository at
`/tmp/trip-planner-1872-browser-ports-commit.git`, with a patch and bundle at
`/tmp/trip-planner-1872-browser-ports.patch` and
`/tmp/trip-planner-1872-browser-ports.bundle` for the owning automation to apply.
GitHub API access failed, preventing PR checklist/comment/label updates and
confirmation that PR #1872 is open and ready for review. Hosted checks and
exact-head review gates remain required after applying the commit.
