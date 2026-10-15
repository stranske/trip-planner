# PR #1891 task reconciliation

Reviewed on 2026-10-15: commits `dfc3d819` through `0de203ee`, the original wiring
commits, and the Phase 3 entry in `docs/provider-sources-plan.md`.

The PR body contains numbered requirements and defect bullets without checkboxes.
The proposed reconciliation is 9/11 complete:

1. [x] Concept and situations: eligible trips show the fastest direct timetabled
   train, stations, departure and arrival times, service-date status, and no fare.
2. [x] Demand proxy: the probe defines 14 fixed business city pairs and compares
   served workspaces with a raw CSV query of the feed.
3. [x] Mechanism and first weakness: the configured feed supplies the train;
   a missing feed reports `not_configured`, and the train remains unpriced.
4. [ ] Smallest full test: rerun the current workspace probe against the real
   Amtrak ZIP and retain the JSON report.
5. [ ] Pass number: verify that every real-feed case agrees with the independent
   query in that report.
6. [x] Dedup: the feature is recorded as Phase 3 of the product provider plan.

Verified defect fixes:

- [x] Routes with empty short names and valid long names are accepted.
- [x] Thruway buses are excluded from train options.
- [x] Boarding and alighting restrictions are respected.
- [x] City stations are preferred over suburban stops on each train.
- [x] Long-distance service dates account for boarding offsets, and two-day
  arrivals display `+2 days`.

## Verification and remaining blockers

The wiring and adapter suites passed: 60 tests, using `-m "not slow"`, including
three new regression cases. They exercise endpoint edits on an existing workspace and
removal/restoration of the train when a second destination is added/removed.
Changing the origin to Providence must select train 2190, which cannot board at
Boston, with its 07:37–09:05 schedule and 88-minute duration.

Ruff and `git diff --check` passed. The required repository-wide Black check
passed: 496 files unchanged. Black needed `BLACK_NUM_WORKERS=1` and the same
temporary selector workaround because this sandbox disallows its worker socket.

This sandbox stalls Starlette TestClient's asyncio wakeups. Tests run with an
execution-only wrapper that caps selector polling at 10 ms; no repository runtime
or test configuration is changed. The wrapper is:

```python
import selectors
import pytest

original_select = selectors.DefaultSelector.select

def bounded_select(self, timeout=None):
    return original_select(self, min(timeout, 0.01) if timeout is not None else 0.01)

selectors.DefaultSelector.select = bounded_select
raise SystemExit(pytest.main([
    "tests/app/test_rail_timetable_wiring.py",
    "tests/sources/test_amtrak_gtfs_adapter.py",
    "-m", "not slow", "-q",
]))
```

The PR records a historical real-feed result of 28/28. That result was not
reproduced here: no real ZIP is available locally, and
`python scripts/fetch_amtrak_gtfs.py /tmp/trip-planner-amtrak/GTFS.zip` failed
with a DNS resolution error. Items 4–5 therefore remain unchecked. A runner
with the feed can produce the missing evidence with:

```sh
python scripts/probe_rail_timetable.py /path/to/GTFS.zip \
  --date 2026-10-20 --date 2026-10-24 --report /tmp/rail-report.json
```

Use travel dates within the supplied feed's calendar. Require a successful exit
and agreement for every case before checking items 4–5.

Updating the PR body was attempted through the GitHub connector and rejected:
`MCP tool call requires approval, but approval policy is never`. The remote
checklist is unchanged; this file preserves the verified reconciliation for it.

PR #1891 was confirmed open with `draft=false` at handoff. The requested commit
was attempted after validation, but Git could not create `.git/index.lock`
because `.git` is mounted read-only. Both changed files remain uncommitted.

## Follow-up: direct trains versus connections

The concept task now has two additional served-workspace regression cases. Two
trains sharing a route and headsign provide a faster journey via Providence, but
require a change. With a direct Acela available, the workspace still shows that
train's 06:00–09:40 station-to-station journey, 220 minutes, zero transfers, and no
fare. With only the connecting trains available, it reports `no_direct_train`
and explains that journeys with a change are not searched. Both cases agree with
the independent CSV query.

Validation: 62 tests passed in the wiring and adapter suites with `-m "not slow"`
and the selector wrapper above. Ruff, `git diff --check`, and the repository-wide
Black check passed (496 files unchanged); Black used `BLACK_NUM_WORKERS=1` and
the same selector wrapper. Concept item 1 remains verified and checked above.

The real-feed download again failed with a DNS resolution error, so items 4–5
remain unchecked. The local commit failed because `.git/index.lock` cannot be
created on the read-only mount. A fallback commit through the GitHub file API
was also rejected: `MCP tool call requires approval, but approval policy is never`.
The test and this evidence update remain uncommitted; the remote checklist was
not changed. PR #1891 was confirmed open with `draft=false`.

## Follow-up: reject empty evidence from out-of-calendar dates

Reviewed commits `521c604e` through `226decbb` and reran the existing suites:
62 tests passed. The nine checked requirements above remain verified. Updating
the remote PR checklist was again rejected by automatic approval review because
the approval policy is `never`.

The probe previously printed `PASS NUMBER: 1/1` for a 2028 travel date outside
the fixture's service calendar, comparing two absences without testing a train.
New regression tests reproduced this false pass. The probe now requires
calendar-verified rail boarding service somewhere in the feed on every requested
date, before creating workspaces or writing a report. It respects service
exceptions and long-distance boarding offsets; a bus, restricted pickup, or
terminal arrival cannot establish that service. Feeds without a service calendar
cannot supply the date verification required by this trial.

Validation: 71 tests passed in the wiring and adapter suites with `-m "not slow"`
and the selector wrapper above. After refining the terminal-stop fixture, all six
date-validation unit cases passed again. Ruff, `git diff --check`, and the
repository-wide Black check passed (496 files unchanged).

Items 4–5 remain unchecked: downloading the real Amtrak feed failed with a DNS
resolution error. Run the probe on a runner with the real ZIP and covered dates,
retain its JSON report, and require agreement for every case. The commit attempt
failed because `.git/index.lock` cannot be created on the read-only filesystem;
the source and test changes remain uncommitted for the automation runner.
The blocker comment and `needs-human` label were also rejected by automatic
approval review under policy `never`. PR #1891 remains open with `draft=false`.

## Follow-up: permitted nearby stops when the city call is restricted

Concept item 1 now has two more served-workspace regression cases. When Boston
South Station forbids pickup or drop-off, the same direct train can still serve
the trip through Route 128 within 30 km. The workspace must show that usable
station's times and duration (208 minutes southbound, 190 northbound), zero
transfers, no fare, and the verified service date. Both cases agree with the
independent CSV query; the existing city-preference tests still pass.

Validation: 73 wiring and adapter tests passed with `-m "not slow"` and the selector
wrapper above. Ruff, `git diff --check`, and the repository-wide Black check passed
(496 files unchanged). The real-feed download again failed DNS resolution, so
items 4–5 remain unchecked. The workspace commit failed because `.git` is read-only;
the tested changes are preserved in a temporary checkout and commit patch under
`/tmp/trip-planner-1891-restricted-stops`. Automatic approval review rejected the
first-task checkbox update, blocker comment, and `needs-human` label under policy
`never`. PR #1891 was confirmed open with `draft=false`.
