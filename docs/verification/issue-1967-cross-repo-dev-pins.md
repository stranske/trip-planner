# Issue #1967: retained repair and exact-target acceptance

Check date: 2026-11-11 (America/Chicago).

Outcome 1: the real workflow-pinned TPP checkout and current planner requirements
pass the pin guard, including a deliberate return to the original incompatible
producer followed by byte-for-byte restoration.

```sh
TPP_REPO_PATH=/private/tmp/issue2017-tpp /opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
```

Stop rule: two failed repair attempts or 45 minutes from 18:46 UTC. Run only
the focused pytest module; do not run the full suite locally.

## Source reconciliation

PR #1990 is closed and unmerged. Its useful dependency pairing and workflow
guard have since reached main through other deliveries, including #2005 and
#2018. Retain current Ruff 0.17.4, mypy 2.4.1, pytest 9.2.0, and TPP revision
`5c9ec6e15ac959023b9fc9cdd1099d70a6073396`. Reapplying #1990's older TPP
revision would reintroduce the later Ruff conflict.

The planner metadata at #1966 head
`164ed1a02b126e72ce407620829e40aa92925a53` has Git blob
`9721fb639a0389d6ab8527f04dda6d4641668e66`, identical to the existing
`tests/fixtures/issue_2025_ledger/failed-trip-planner.toml`. The historical
guard and offline pip tests therefore already exercise the original planner
input together with TPP `acc4aeddee5f4ffefbdc73fcb07505cd3d198197`.
This PR strengthens that guard's regression to require the exact conflicting
versions, preserving the finished source repair without another pin change.

## Acceptance evidence

- Before and after the regression extension, the focused command above passed
  **45 tests, zero skips**, including both real-checkout checks and offline pip
  resolution. The final result was **45 passed in 3.03 seconds**.
- Deliberately replaced only the workflow's TPP ref with original producer
  `acc4aeddee5f4ffefbdc73fcb07505cd3d198197`. Running
  `pytest tests/scripts/test_cross_repo_dev_pins.py::test_workflow_tpp_pin_resolves_with_planner_dev_pins -q`
  through `/opt/anaconda3/bin/python3 -m` failed in 0.35 seconds (exit 1), naming
  incompatible Ruff, mypy and pytest pins. A `finally` block restored the exact
  workflow bytes; the same check passed in 0.31 seconds (exit 0).
- Removing the diagnostic versions while retaining conflict detection makes
  `test_smoke_pin_guard_with_historical_editable_checkouts[issue-1967-original-install-inputs]`
  fail at the new exact-message assertion. Restoring the exact test-module bytes
  makes the same regression pass. This verifies the added assertion's sensitivity.
- The owner-directed fallback interpreter is Python 3.12.2; no repository venv
  exists. These are focused dependency-metadata results, not a supported-runtime
  application test. The full suite was not run.

Fresh GitHub readback:

```sh
gh run view 41674233862 --repo stranske/trip-planner --json conclusion,headSha,status,url
gh run view 43035261628 --repo stranske/trip-planner --json conclusion,headSha,status,url,jobs
```

The original evidence run remains **failure** on #1966 head
`164ed1a02b126e72ce407620829e40aa92925a53`. PR #1966 remains **closed,
unmerged**. Current-main smoke run
[43035261628](https://github.com/stranske/trip-planner/actions/runs/43035261628)
passes `cross-repo-full-product` on
`114ca378c040c609fe0d25e301318dcc00e81bbb`; it does not prove a regenerated
#1966 gate.

The canonical sync-core log's latest retained entry for #1966 is round
`20261105T054444Z`, recorded at `2026-11-05T05:45:07Z`: disposition and terminal
are `superseded`, reasons and handoffs are empty. This predates the subsequent
source fixes, so it is not the requested post-repair classification. Later
#2006 evidence in `docs/verification/issue-1973-dev-tool-pins.md` has no formal
native replacement edge from #1966; do not substitute it silently.

## Remaining operational acceptance

The literal regenerated-#1966 gate and next-round classification are **not
complete**. No generated sync PR was hand-edited. The named Maint 68 workflow
syncs consumer templates; #1966 was produced by Maint 52 dev-tool sync (the
same distinction is recorded for #1972/#2006). Dispatching Maint 68 cannot
establish a regenerated dev-tool #1966, and reviving the obsolete failed
delivery would reintroduce old pins. This PR retains the correct current
source instead of manufacturing that evidence.

Blocking/drainable pair: exact-target downstream acceptance missing / the
owning sync-core delivery lane can establish an explicit successor for #1966,
regenerate it through the actual dev-tool producer, verify its exact-head
cross-repo gate and capture the subsequent canonical classification. This is
an unresolved acceptance dependency, not a new gate or a claim of completion.
No automatic merge is enabled by this repair.

## Keepalive follow-up: offline break and restoration

Check date: 2026-11-11 UTC. This sandbox uses Python 3.14.10, Black 26.10.1,
Ruff 0.17.4 and mypy 2.4.1. The earlier Python 3.12.2 fallback results above
describe the owner's environment; that interpreter is not available here.

The `all` case of
`test_offline_workflow_guard_rejects_original_producer_pins` now selects the
actual original producer `acc4aeddee5f4ffefbdc73fcb07505cd3d198197` and its
complete reviewed metadata. It calls the named
`test_workflow_tpp_pin_resolves_with_planner_dev_pins` check and verifies all
three conflicts. Each case then restores the current workflow selection and
the current producer's exact metadata and requires that same check to pass.
All workflow changes take place in temporary test fixtures. The repository's
protected workflow and dependency pins remain unchanged.

The historical regression now requires the complete ordered diagnostic lines,
including all three exact version pairs and the full repair guidance. Pytest's
added assertion indentation and expression trace are excluded from this comparison.

- [ ] Reproduce the literal owner command with **45 passed, zero skips**.
  `/opt/anaconda3/bin/python3` and `/private/tmp/issue2017-tpp` are absent.
  `python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q -m "not slow"`
  passes **43 tests with 2 skips**; both skips require a live producer checkout.
  Git cannot resolve `github.com` to obtain that checkout. Reviewed metadata
  fixtures are not a substitute for live-checkout acceptance.
- [ ] Repeat the literal workflow-file break and restoration. Protected workflow
  edits are not authorized in this run. The isolated original-ref regression
  and all three single-tool break/restoration cases pass instead.
- [x] Remove version diagnostics: extended regression fails; exact restoration
  passes. Removing Ruff, mypy and pytest diagnostics separately produces an
  expected failure in the historical regression on each of the three runs.
  Restoring the exact test-module bytes returns that regression to **1 passed**.
- [x] Only focused pytest checks ran locally. Python 3.12.2 remains the
  owner-directed fallback; supported-runtime application validation relies on
  hosted checks. This sandbox instead used Python 3.14.10 for the focused
  module, with `-m "not slow"`; no application suite ran.

Focused Ruff and mypy checks pass. The required repository-wide command
`black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`
passes with **530 files left unchanged**. Individual checks populated
`BLACK_CACHE_DIR=/tmp/issue1967-black-cache` first; the global check then ran
with that cache and `BLACK_NUM_WORKERS=1` because uncached multi-file checks
do not finish in this sandbox. No downstream regeneration or classification
criterion is inferred from these offline test results.

Commit handoff is blocked: `git add` cannot create `.git/index.lock` because
the repository's Git directory is mounted read-only. The patch is saved at
`/tmp/issue1967-keepalive.patch` for application from a writable checkout.
Adding `needs-human` and posting the blocker comment through the GitHub
connector were denied because those tools require approval and this run's
approval policy is `never`. Fresh PR readback shows #2029 open and ready for
review; no PR or branch was created by this run.
