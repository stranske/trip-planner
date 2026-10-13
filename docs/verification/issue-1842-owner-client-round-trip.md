# Issue 1842: production owner-client round trip

Three new integration cases advance the first handoff task. They use a real
persisted login session, the production proposal routes, OwnerPortalReceiptClient,
HTTP serialization, receipt validation, and database persistence without dependency
overrides. Only the producer network boundary returns synthetic responses. These
tests establish consumer behavior; they do not prove accepted producer behavior.

The cases cover approved, rejected, and changes-requested decisions. Each verifies
server-owned answers and HTTPS origin, initial unknown submission/decision state,
submitted and pending-review observations, a correlated recorded decision, and
retrying without creating another producer draft. Retries issue a new browser
capability while preserving the saved preparation time and decision. Public
workspace reads expose neither owner authority nor internal snapshots, receipts,
or browser capabilities.

Task reconciliation:

- [ ] Complete the browser handoff and accepted producer integration. Consumer
  preparation is wired and tested, but real browser and accepted pinned producer
  verification remain outstanding.
- [x] Bind the handoff to saved trip, prices, and policy-result hashes. Existing
  saved-handoff and preparation tests verify changed and concurrent facts fail
  before an obsolete handoff can be returned.
- [x] Reject caller-selected destination and handoff facts. Request-boundary,
  preparation, and session-owner tests verify rejection before producer effects.
- [x] Enforce HTTPS outside local/test environments. Portal-origin tests pass.
- [x] Keep internal source snapshots and receipt authority server-side. Existing
  persistence tests and all three new round-trip cases verify public projection.
- [ ] Prove the full authenticated two-app manager decision/status return against
  an accepted producer revision. The PR's previously checked acceptance item is
  premature; producer issue stranske/Travel-Plan-Permission#1658 remains open.

The old no-receipt-endpoint criterion is superseded by the owner's authenticated
status-return authorization. Unknown state remains required until a validated,
owner-bound receipt supplies the correlated producer state.

Baseline validation on 2026-10-13, with `-m "not slow"`:

- Handoff flow/request, preparation, session ownership, saved handoff, and origin
  suites: 579 passed.
- Saved-handoff, preparation, and workspace receipt suites: 196 passed.
- New production owner-client cases: 3 passed, 57 deselected.

Final verification:

- `python /tmp/trip-planner-test-runner.py
  tests/integration/test_workspace_portal_preparation.py
  tests/integration/test_workspace_portal_receipt.py
  tests/integrations/test_tpp_portal_receipt_client.py -q -m "not slow"`:
  159 passed, including all three new cases.
- Ruff and `git diff --check` passed.
- Repository-wide Black check (line length 100, excluding `.workflows-lib` and
  `node_modules`): 489 files unchanged. The same selector wait workaround was
  applied by `/tmp/trip-planner-black-runner.py`, with one Black worker.
- `python scripts/measure_complexity.py --changed-from origin/main --max-complexity 25`:
  55 functions passed.

These suite counts overlap and must not be added together. The ASGI tests use a
temporary runner at `/tmp/trip-planner-test-runner.py` that caps selector waits to
one millisecond because sandbox asyncio wakeups otherwise stall. Test assertions,
authentication, and product code are unchanged by this environment workaround.

Frontend dependency installation with
`npm --prefix frontend ci --offline --ignore-scripts --no-audit --no-fund` fails
because xmlchars is absent from the offline cache. No frontend pass is claimed.
No pinned TPP checkout is present, so no real producer pass is claimed.

The reconciled PR body is preserved at `/tmp/pr-1872-reconciled-body.md`.
The GitHub connector rejected the metadata update because approval is required
while this run's approval policy is `never`. PR #1872 was read as open and ready
for review. The original `.git` is read-only, so the source commit is retained
in an isolated writable Git directory for the owning lane to apply.
