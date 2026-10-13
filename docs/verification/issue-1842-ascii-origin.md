# Issue 1842: require an ASCII handoff hostname

This round advances the first unchecked task's fixed-origin browser POST. Python
accepted Unicode hostnames that native forms reject or normalize differently:
`tpp。123` is rejected by Node's browser-compatible URL parser, `１２７．１`
becomes `127.0.0.1`, and a zero-width space is removed from `tpp.example`.

The server now requires an ASCII hostname before applying the existing numeric
host and HTTPS checks. International domains must be configured using their ASCII
Punycode spelling. `https://xn--bcher-kva.example:8443` remains supported and produces
the same absolute `/portal/handoff` action in the browser URL parser.

Regressions cover both configuration variables and local, test and production
environments. Saved-verdict route tests cover eligible and already-prepared state:
invalid configuration returns 503 without changing the saved proposal or trip
timestamp; correcting it permits preparation using the same fields and hash.
Manager submission and decision remain unknown, and private snapshots stay private.

Validation on 2026-10-11:

- Before the fix, all 30 new Unicode rejection cases failed; the ASCII Punycode
  case and 190 existing handoff checks passed.
- `pytest tests/integrations/test_tpp_portal_handoff.py
  tests/integration/test_saved_portal_handoff.py
  tests/app/test_proposal_handoff_schema.py -q -m 'not slow'`: 244 passed.
- `pytest tests/app/test_portal_handoff_flow.py tests/app/test_proposal.py
  -q -m 'not slow'`: 133 passed.
- Relevant-file Black formatting and the required repository Black check at line
  length 100 passed: 481 files unchanged. Ruff, mypy for the three changed Python
  files, and `git diff --check` passed.

The HTTP route tests and Black used a temporary one-millisecond selector timeout
cap in `/tmp/trip-planner-handoff-ascii/sitecustomize.py` because this sandbox blocks
asyncio socket wakeups. No repository code or assertions were changed for this
runner adjustment. The HTTP test run completed in 46.28 seconds; shorter timed
attempts did not finish and are not counted as passing.

The shared `.git` mount is read-only. The source commit is preserved in a writable
checkout at `/tmp/trip-planner-handoff-ascii-commit`, with a commit patch and bundle
in `/tmp/trip-planner-handoff-ascii`. The GitHub connector rejected the requested
`needs-human` label because it requires approval and this run's policy is `never`.
No task checkbox is marked complete. Pinned-producer integration, authenticated
status return and hosted checks remain outstanding.
