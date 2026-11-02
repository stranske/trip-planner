# Issue 1962: real contract probe origin

The shared full-product trip creator already supplies Seattle as the origin.
The unmocked regression now also checks that the real trip routes persist that
origin and that the destination pair measures distinct inter-city travel times
above the 45-minute local-only fallback. A change in another metric cannot hide
that fallback. The origin assertion requires exactly two Seattle observations,
so missing trip-route evidence cannot satisfy it through an empty `all()`.

Verified acceptance on 2026-11-02:

- [x] Replayed the real contract report before the fix: removed only the Seattle
  origin from `_create_trip`, then called `run_contract_report()` without mocks.
  TP3 returned `FABRICATED`; both destinations reported 45 minutes.
- [x] Ran `python -m pytest -q tests/scripts/test_check_full_product_verification.py
  -m "not slow"`: **28 passed**, 6 existing Alembic deprecation warnings. The
  latest run took 22.90 seconds; the supplied 5.01-second timing was not reproduced.
- [x] Deliberate break: with the origin removed,
  `test_contract_report_tp3_not_fabricated_without_monkeypatch` failed with
  `FABRICATED`. Restored the script byte-for-byte in a `finally` block and reran
  the named regression: **1 passed** in 6.70 seconds. The restored real report
  returned `PARTIAL` with the destination travel times below.

| Origin in probe input | TP3 verdict | Chicago minutes | Reykjavik minutes |
|---|---|---|---|
| Omitted | FABRICATED | 45 | 45 |
| Seattle | PARTIAL | 410 | 643 |

Both destination observations used one traveler and the same three-day duration.
The party-size pair still reports 410 minutes for both one and eight travelers,
so `PARTIAL` remains the accurate verdict. This change does not claim that all
comparison determinants work.

The sandbox blocks asyncio socket wakeups: the initial ordinary pytest run
stalled at TestClient startup. Successful report and pytest runs used the
repository's documented temporary selector polling workaround via
`PYTHONPATH=/tmp/tp1962-validation`. It caps selector waits at 10 milliseconds;
application routes, scenario calculations, and test assertions are unchanged.

The required repository-wide Black check passed: **518 files unchanged**, using
`BLACK_NUM_WORKERS=1` with the same temporary selector polling workaround.

The workspace's `.git` is mounted read-only, so `git add` fails creating
`.git/index.lock`. The verified changes remain in the workspace; a recovery
commit and Git bundle are saved under `/tmp/tp1962-review` and
`/tmp/tp1962-probe-origin.bundle` respectively. Applying that commit to the PR
branch requires a writable Git checkout.

GitHub rejected the prior blocker comment and `needs-human` label requests, as
well as this iteration's PR-body checkbox reconciliation, because the environment's
approval policy is `never`; none of these updates was applied. All three
validation tasks are verified above; their PR-body checkboxes still require reconciliation.
PR #1963 was verified open with `draft=false` after those attempts.
