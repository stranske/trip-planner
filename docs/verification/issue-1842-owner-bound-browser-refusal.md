# Issue 1842: preserve producer state when refusing the legacy browser handoff

This round advances the first unchecked task through regression tests. The
existing service guard refuses a legacy native-form preparation once a trusted
producer binding exists. Its prior test covered one approved decision through
the service; the new tests exercise the public route's 409 translation and
persisted state across 28 combinations.

The cases cover an unobserved producer binding, prepared and submitted receipts,
pending review, and approved, rejected and changes-requested decisions. Each is
checked with and without an available observation and configured portal origin.
Two consecutive preparation attempts must preserve the full private binding,
receipt, verdict, public metadata and persisted update times. They must neither
map traveler form fields nor perform another producer identity or receipt lookup.
Public errors must omit the producer handoff and draft identifiers.

Validation on 2026-10-12:

- The four focused backend suites passed 415 tests with `-m "not slow"`.
- The final new route matrix passed all 28 cases after the final test edit.
- Repository-wide Black at line length 100 passed: 485 files unchanged.
- Changed-file Ruff and `git diff --check` passed.
- Black used the documented sandbox selector-wait workaround under
  `/tmp/trip-planner-owner-bound-checks`; pytest needed no runner workaround.

This is a test-only change. No parent checkbox is marked complete. Authenticated
producer preparation, traveler answer collection, identity bridge provisioning,
frontend verification and the pinned two-app contract remain outstanding.
GitHub API connectivity failed, so hosted checks and PR readiness were not
verified. The shared `.git` mount also refused staging; a source commit, patch
and bundle are preserved under `/tmp/trip-planner-owner-bound-handoff-commit`.
