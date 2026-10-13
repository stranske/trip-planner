# Issue 1842: authenticated prefill validation

This change advances the first unchecked handoff task. Authenticated preparation
previously bypassed the legacy browser response's prefill field validation before
forwarding answers to TPP. A regression reproduced acceptance of an empty prefill.
Both paths now share the existing nonempty, 15-field contract and validate before
owner resolution, producer calls, or persistence. Validation errors omit input
values from the public error and its logged exception message.

Eight new regressions cover empty mappings and unsupported internal snapshots,
return URLs, and traveler-completed destination ZIP answers, on initial preparation
and bound retries. They verify unchanged saved state and recovery with the real
mapper. Another 24 production HTTP cases reject caller-selected destinations,
fields, bindings, URL facts, and form bodies before producer side effects on both
preparation and status routes. Valid retries retain server-owned facts and unknown
manager submission/decision state.

Validation on 2026-10-12:

- Initial handoff baseline: 384 passed with `-m "not slow"`.
- Preparation and response schema checks: 65 passed; the final implementation's
  eight mapper regressions also passed independently.
- Broader handoff, preparation, receipt, schema, and application regression suite:
  726 passed with `-m "not slow"`.
- Required repository-wide Black check at line length 100: 488 files unchanged.
- Mypy passed for both changed production files; the exact complexity command
  `python scripts/measure_complexity.py --changed-from origin/main --max-complexity 25`
  passed for 57 functions. Handoff preparation has complexity 22.
- Ruff passed for the schema and tests. The service retains the same three Ruff
  findings present at HEAD (`RUF059`, `I001`, `TRY004`); no new findings were added.
- `git diff --check` passed.

ASGI tests and Black used the previously documented one-millisecond selector wait
cap, here in `/tmp/trip-planner-authenticated-boundary/sitecustomize.py`. Black also
used `BLACK_NUM_WORKERS=1`. Repository test assertions and validation rules were
unchanged by that environment workaround.

No task checkbox is marked complete. Browser verification, accepted pinned TPP
integration, and hosted checks remain outstanding. GitHub is unreachable, so PR
readiness and blocker-comment/label updates could not be verified. The checkout's
read-only `.git` prevents staging; a source commit, patch, and bundle are preserved
under `/tmp/trip-planner-authenticated-boundary` for the owning writable lane.
