# Issue 1842: cancel delayed browser handoffs

The first task already prepares a server-owned native POST form from a saved
verdict. Its browser action previously remained active after the requesting
workspace unmounted or reloaded. A delayed preparation response could therefore
post the previous workspace's form after the traveler had left it.

The workspace now cancels pending browser actions on reload and unmount. An old
response cannot update the current handoff metadata, display an old error, submit
its form, or clear a newer request's busy state. A fresh attempt remains available.
Cancellation does not undo server preparation or claim submission or a decision.

Three frontend regression cases cover leaving the workspace and resolving or
rejecting an old request while a fresh request is pending after reload. These
cases have been added but **have not run in this environment**.

Validation on 2026-10-11:

- Existing backend handoff baseline: 137 passed across
  `tests/integrations/test_tpp_portal_handoff.py` and
  `tests/integration/test_saved_portal_handoff.py`, with `-m "not slow"`.
- Existing app handoff/proposal/schema baseline: 113 passed across
  `tests/app/test_portal_handoff_flow.py`, `tests/app/test_proposal.py`, and
  `tests/app/test_proposal_handoff_schema.py`, with `-m "not slow"`.
- `tsc --noCheck --noEmit --project frontend/tsconfig.json` passed. This checks
  TypeScript syntax; it is not a type check or a behavioral test.
- Full repository Black check at line length 100 passed: 481 files unchanged.
- `git diff --check` passed.

The app test process used `/tmp/trip_planner_handoff_checks/sitecustomize.py` to
cap selector waits at 10 milliseconds because the sandbox blocks asyncio
socketpair wakeups. Repository code and assertions were unchanged.

Frontend checks remain blocked: the offline npm cache lacks `xmlchars-2.2.0.tgz`,
registry DNS resolution fails, and `npm test -- src/lib/tppPortalHandoff.test.ts
src/routes/WorkspacePage.test.tsx` reports `vitest: not found`. The pinned sibling
TPP checkout is absent. No task or full-product acceptance is marked complete.

Shared-checkout staging is blocked by a read-only `.git` mount. A source commit
is preserved in `/tmp/trip-planner-1872-handoff-cancellation-commit`, with a patch
and bundle for the owning writable lane. PR #1872 was observed open and ready
for review; authenticated correlated status integration and hosted gates remain
outstanding.

The GitHub connector rejected the blocker comment and `needs-human` label: both
require approval, while the current approval policy is `never`. Neither mutation
was applied. The PR remained open and ready for review at its original head.
