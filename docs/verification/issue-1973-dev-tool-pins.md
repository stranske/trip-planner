# Issue #1973: dev-tool pin verification

## Outcome and scope — 2026-11-08

The required focused check passes: 79 tests on supported Python 3.13.13 against
the workflow-pinned producer, followed by a deliberate Ruff conflict failure and
restoration pass. The regenerated delivery's exact-head cross-repo gate passes, and the next
controller-owned sync-core classification records delivery without this finding.

Before edits, the real-input outcome was defined as: the named focused pytest
command passes without skips against the exact producer, the incompatible copy
fails naming both Ruff requirements and passes after restoration, and the
regenerated delivery passes its cross-repo gate with the finding absent from the
next controller classification. Check date: 2026-11-08. Stop rule: three failed
attempts at a required step or 45 minutes. Only this evidence file is changed.

## Integrated implementation and complete review

Current GitHub readback of [#2005](https://github.com/stranske/trip-planner/pull/2005)
reports `MERGED`, merged at `2026-11-08T11:44:37Z`, source head
`b20e73f66422d12f255aca4e2e35858f21c37781`, and merge commit
`29c6aa01064f9eb3cbf15debd32cac3327ec43b8`. A fresh fetch established that main
contains that merge. `git diff --quiet` between the fetched source head and merge
commit exited 0: their complete trees match. The old review-floor refusal is
historical and does not describe current integration.

Reviewed all nine paths in the merged diff, including the complete 535-line
`tests/scripts/test_cross_repo_dev_pins.py` and 347-line
`tests/scripts/test_cross_repo_smoke_workflow.py`. Retain the implementation:

- The producer snapshot and live guard check both runtime/dev metadata and the
  exact workflow-pinned checkout HEAD, isolating inherited Git location variables.
- Compound/prefix constraints and repeated runtime/dev requirements have regression
  coverage. Original-producer cases exercise all three tool conflicts separately.
- Offline pip resolver tests use metadata-only wheels with each project's `[dev]`
  extra, require `ResolutionImpossible` and both conflicting requirements, and
  verify the successful resolution report. They prove the selected tool resolution,
  not a complete real-package installation.
- Workflow assertions require the live compatibility check before joint producer
  installation. Existing integration exports and client-method guards remain.
- The remaining merged changes pair the producer revision and dev pins, add the
  `packaging` test dependency, and align the design-map/evidence documentation.

The provisioned `closer-r1/issue-1973` branch already contained evidence commit
`e2a3ed5ab14548d6820a839e81685b6e48787a4e` and ready PR
[#2011](https://github.com/stranske/trip-planner/pull/2011). No other local
`closer*/issue-1973` branch existed. That commit is retained; its unsupported
“All acceptance criteria are met” and “None” remaining-unknown claims are
superseded here. No replacement implementation or evidence PR is created.
No dependency pins, lockfiles, implementation, or tests are edited by this repair.

## Required-runtime local evidence

No repository `.venv` exists. `.python-version` selects deployment Python 3.14;
`pyproject.toml` supports `>=3.13,<3.15`. These focused local repository-command
results use supported Python **3.13.13**, executable
`/opt/homebrew/opt/python@3.13/bin/python3.13`, invoked through
`/opt/homebrew/bin/python3.13`. No full local suite or release/verify pipeline was run.
The original issue's unrestricted full-suite result remains unverified locally;
the checked repair criterion below covers only the two explicitly requested files.
This follows the repair instruction forbidding a full local suite and does not
replace that missing full-suite evidence with source-PR CI.

The producer checkout is clean at
`/Users/teacher/.codex/orchestrator/worktrees/Travel-Plan-Permission`, HEAD
`b56d92b389736c70370aa9134f379ac8cd1f3ad1`, matching `TPP_PINNED_REF`.
The passing live snapshot test also verifies its runtime/dev requirements.

```sh
TPP_REPO_PATH=/Users/teacher/.codex/orchestrator/worktrees/Travel-Plan-Permission /opt/homebrew/bin/python3.13 -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q
```

Observed output, exit **0**:

```text
........................................................................ [ 91%]
.......                                                                  [100%]
79 passed in 3.20s
```

Created `/tmp/issue-1973-producer-p07xzrhs` using `git archive` of that exact
producer commit. Changed only the isolated copy's `pyproject.toml` from
`ruff==0.17.3` to `ruff==0.17.2`; the real producer checkout was untouched.

```sh
TPP_REPO_PATH=/tmp/issue-1973-producer-p07xzrhs /opt/homebrew/bin/python3.13 -m pytest tests/scripts/test_cross_repo_dev_pins.py::test_planner_dev_pins_resolve_with_pinned_tpp_checkout -q
```

Observed output excerpt, exit **1**, expected:

```text
AssertionError: trip-planner and the pinned TPP revision cannot be installed together:
  ruff: trip-planner 'ruff==0.17.3' vs TPP 'ruff==0.17.2'
Move TPP_PINNED_REF in .github/workflows/cross-repo-smoke.yml to a TPP revision with matching pins, in the same PR as the pin update.
FAILED tests/scripts/test_cross_repo_dev_pins.py::test_planner_dev_pins_resolve_with_pinned_tpp_checkout
1 failed in 0.19s
```

Restored the copy's original metadata byte-for-byte; `cmp` with the real pinned
checkout's metadata exited **0**. Repeated the same pytest command, exit **0**:

```text
.                                                                        [100%]
1 passed in 0.14s
```

## Producer regeneration and delivery linkage

Original delivery [#1972](https://github.com/stranske/trip-planner/pull/1972)
is closed without merging, at head
`d679b90ac41e91f80fa96f4b43cd05a28f592680`. Issue #1973 originally records its
pin-conflict finding from sync-core round `20261105T030005Z`. #2005's merged
commit explicitly names #1972 and fixes that same incompatible producer/tool pair.

[#2006](https://github.com/stranske/trip-planner/pull/2006) is the current delivery
of those dev-tool versions, generation `91791b44e525`, plan
`dev-tool-91791b44e525`. Its predecessor/successor arrays are empty: the evidence
establishes a shared payload/failure and current delivery, not a formal native
replacement edge from #1972. The named producer is Maint 52 Sync Dev Versions;
Maint 68 is the generic source-sync path named in the original issue.

After confirming no active Maint 52 run and unchanged canonical tool versions,
requested only this consumer through the producer:

```sh
gh workflow run maint-52-sync-dev-versions.yml --repo stranske/Workflows --ref main -f repos=stranske/trip-planner -f dry_run=false
```

[Producer run 42484255917](https://github.com/stranske/Workflows/actions/runs/42484255917)
concluded **success**, including `Sync stranske/trip-planner`. It regenerated
existing #2006 at head `fcb6e97a291bd620629aa228561d36c3ee6cdf0d` on base
`29c6aa01064f9eb3cbf15debd32cac3327ec43b8`, retaining the generation and recording
source commit `e8f9dc2373563dea50a708501a63a9ad58f8db06` and desired tree
`52a50c1ce7ac5ca86891f5dea3ce26d01f591c16`. No generated branch was edited manually.
The owning delivery lane subsequently merged #2006 at `2026-11-08T13:23:04Z`,
merge commit `419015e6035cc77db18de3ab58c60651d8e51bc8`. This repair branch
merges that current main while preserving the pre-existing evidence commit;
its net PR diff still changes only this document.

## Regenerated-head gate

```sh
gh run view 42484305671 --repo stranske/trip-planner --json headSha,conclusion,jobs
gh run view 42484305260 --repo stranske/trip-planner --json headSha,conclusion,jobs
```

Both commands exited **0** and returned head SHA
`fcb6e97a291bd620629aa228561d36c3ee6cdf0d`, equal to current #2006 head:

| Run | Overall conclusion | Named job | Job conclusion |
| --- | --- | --- | --- |
| [Gate 42484305671](https://github.com/stranske/trip-planner/actions/runs/42484305671) | success | Cross-Repo Smoke / cross-repo-full-product, job 128742800569 | success |
| [Cross-Repo Smoke 42484305260](https://github.com/stranske/trip-planner/actions/runs/42484305260) | success | cross-repo-full-product, job 128742727094 | success |

Gate's `gate-summary` also succeeded. This is regenerated-delivery evidence,
separate from the earlier successful source-PR runs. The prior #2006 Gate
`42449207902` failed at producer installation on old head
`4ea6a28d050bbcf2233b725de13ade495f132002`; that failure remains historical.

## Subsequent controller-owned classification

The controller launch log records `2026-11-08T13:30:16Z start apply`.
Its next completed canonical round, `20261108T133016Z` at
`2026-11-08T13:30:21Z`, retained this #2006 item in
`~/.codex/orchestrator/sync-core/rounds.jsonl`:

```json
{
  "target": "stranske/trip-planner#2006",
  "disposition": "delivered",
  "terminal": "delivered",
  "error": null,
  "handoffs": [],
  "owner": "-",
  "reasons": ["merged 2026-11-08T13:23:04Z; 1 files, 0 mismatches"]
}
```

The canonical target state also binds `last_round: 20261108T133016Z` to head
`fcb6e97a291bd620629aa228561d36c3ee6cdf0d`. The pin-conflict finding is absent
from both the reasons and handoffs. This was the existing controller's apply
round, not an independently run classifier or a replacement state directory.
The old #1972 target remains historically `superseded`; its finding is discharged
through the regenerated #2006 delivery described above.

## Repair acceptance

- [x] Inspect the complete merged or current PR diff, including omitted resolver tests, and establish #2005 integration from current GitHub state.
- [x] Record a required-runtime local repository test result and a deliberate incompatibility failure followed by restoration and pass.
- [x] Establish the regenerated delivery's relationship to #1972, verify its current-head cross-repo gate, and obtain the next controller-owned classification without this finding.

Blocking/drainable pair for the repaired finding: blocking 0, drainable 0 /
retain the successful producer, delivery and controller evidence. The evidence
PR still follows its normal CI/review lifecycle. The original unrestricted full
local suite remains unverified under this repair's explicit test restriction;
no formal predecessor edge was added to the producer metadata. Source-PR CI and
issue closure were not used to establish downstream acceptance.

Refs #1973
