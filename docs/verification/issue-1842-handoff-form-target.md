# Issue 1842: explicit browser handoff target

This round advances the first task. The native handoff form now explicitly uses
`target="_self"`. Without that attribute, a document-level `<base target>` could
open the server-prepared form in another window or a parent frame. The handoff
keeps its server-owned absolute destination and POST body.

Three regression cases cover `_blank`, a named window, and `_parent` base targets.
They also check the fixed action, POST method, empty URL query, and unchanged
Unicode and punctuation in the traveler fields. The original native-form test
now checks the explicit target too.

Validation on 2026-10-11:

- Backend handoff baseline: 190 passed across
  `tests/integrations/test_tpp_portal_handoff.py` and
  `tests/integration/test_saved_portal_handoff.py`, with `-m "not slow"`.
- App handoff/proposal/schema baseline: 142 passed across
  `tests/app/test_portal_handoff_flow.py`, `tests/app/test_proposal.py`, and
  `tests/app/test_proposal_handoff_schema.py`, with `-m "not slow"`.
- `tsc --noCheck --noEmit --project frontend/tsconfig.json` passed. This checks
  syntax, not types or browser behavior.
- `git diff --check` passed.

The app tests used a temporary selector timeout cap of one millisecond in
`/tmp/trip-planner-handoff-target/sitecustomize.py` to accommodate the sandbox's
blocked asyncio socket wakeups. Repository code and test assertions were unchanged.

The new frontend regressions remain unverified. Offline npm installation lacks
`xmlchars-2.2.0.tgz`, registry DNS lookup fails, and the targeted frontend test
command reports `vitest: not found`. The installed Chrome browser also fails to
start because the sandbox rejects its socket operation. The pinned sibling TPP
checkout is absent. No task checkbox is marked complete.

The shared checkout's `.git` directory is read-only. The source commit is preserved
in `/tmp/trip-planner-1872-handoff-target-commit`; its patch and bundle are under
`/tmp/trip-planner-handoff-target` for the owning writable lane. The branch is not
pushed by this round. Hosted checks and authenticated correlated status return
remain outstanding.

PR #1872 was observed open and ready for review. GitHub blocked the requested
blocker comment and `needs-human` label because they require approval while this
run's approval policy is `never`; neither mutation was applied.
