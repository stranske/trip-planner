# Issue 2025 acceptance evidence

Checked 2026-11-11T00:19:36+00:00. The executable acceptance checks have evidence. A2 and tasks T1, T3 and T4
still require records in the actual ledger; the proposed patch does not satisfy
that requirement. Workflows main integration is also still open.

The owning regression is published in [Workflows commit
f1ae1a4b8f704bf147938880c0010ded18d51022](https://github.com/stranske/Workflows/commit/f1ae1a4b8f704bf147938880c0010ded18d51022),
branch `codex/issue-2025`, based on `a54f412a4aea3a49241b502abf415bf769e08dea`.
It is not integrated into Workflows main. No second PR was opened, respecting
the one-PR instruction. These consumer artifacts contain no exported Workflows
source or source patch series. The previous implementation remains preserved at
`salvage/pr-2026-d9273628` in trip-planner.

## Resolver verification

From `/tmp/trip-2025-workflows`:

```sh
/tmp/trip-2025-workflows/.venv/bin/python -m pytest tests/test_dependency_resolution.py
```

The venv was created with `/opt/anaconda3/bin/python3` and uses Python 3.12.2,
pytest 9.2.0, and packaging 26.3. This is the fallback expressly permitted by
the issue; Workflows declares Python >=3.13, so supported-runtime CI remains
unverified. No warning policy or tests were disabled. The shared environment
initially failed before collection because of an unrelated pytest-asyncio
plugin; the isolated environment avoids loading that plugin.

At the linked owning commit, the eight-case suite exits 0 in 4.653 seconds.
Changing only the successful TPP fixture's Ruff pin from 0.17.3 to 0.17.2 makes
the same command exit 1 in 3.258 seconds. The successful wheels and editable
cases then print `ResolutionImpossible`. Restoring the original bytes exits 0
in 4.582 seconds. A diff against HEAD confirmed exact restoration. See
`receipts.json`, `baseline.log`, `mutation.log`, and `restored.log`.

The test uses offline metadata wheels and editable metadata preparation for
Ruff, mypy and pytest, including each historical tool mismatch independently.
It calls the production `parse_env_file` and `sync_pyproject` functions against
Workflows' actual `.github/workflows/autofix-versions.env`; one-consumer
propagation fails, and updating both consumers resolves. Full product builds
and runtime dependency installation are outside this bounded test.

Pip gets at most twenty seconds per call and shares a 100-second total budget,
leaving overhead within the issue's two-minute limit. Timeouts report an
explicit resolver failure. `fixture-provenance.json` verifies every historical
fixture's runtime dependencies and dev extra against the four original Git
blobs. TPP extras not selected by `[dev]` are omitted intentionally.

## Historical install and current classification

`failed-install-excerpts.log` and `successful-install-excerpts.log` come from
the issue's two exact `gh run view ... --log` commands. Both runs install the
local editable projects with dev extras. The failed TPP checkout is `acc4aed`;
the successful checkout is `b56d92b`. Ruff moves from 0.17.2 to 0.17.3, mypy
from 2.4.0 to 2.4.1 and pytest from 9.1.1 to 9.2.0, matching planner. The old
PyPI republication proposal is unsupported by those install inputs.

`smoke-run.json` is the exact requested `gh run view 42484305260 --repo
stranske/trip-planner --json headSha,conclusion,jobs` result. It confirms the
successful `cross-repo-full-product` job at final PR head
`fcb6e97a291bd620629aa228561d36c3ee6cdf0d`; `merged-pr.json` independently
confirms #2006 merged on 2026-11-08 at 13:23:04Z.

`sync-core-report.json` retains a fresh read of the subsequent canonical round
`20261108T133016Z`, completed 2026-11-08T13:30:21Z. It explicitly classifies
#2006 as delivered, with zero mismatches, no error and no handoffs. Canonical
target state binds that round to the final PR head. The report also records
Maint 68's `consumer-sync-run-report` artifact path; native template-sync
artifacts do not themselves classify the Maint 52 dev-pin PR. The canonical
sync-core result supplies the acceptance criterion's superseding classification.

## Documented local check and ledger reconciliation

At the linked Workflows commit:

```sh
TMPDIR=/private/tmp npm_config_cache=/private/tmp/trip-2028-npm-cache PATH="/opt/homebrew/opt/coreutils/libexec/gnubin:/tmp/trip-2025-workflows/.venv/bin:$PATH" /opt/homebrew/bin/bash ./scripts/dev_check.sh --verbose
```

Exit 0 at the linked Workflows commit. GNU mktemp honors the writable
`TMPDIR`, Bash 5 supplies `mapfile`, and npm uses a writable cache for the
Renovate validator. The script's mypy and keepalive JS steps suppress their
own exit codes, so this receipt establishes the script's exit status.
See `owner-dev-check.log`.

At the same commit, the focused rerun passed in 4.914 seconds. The Ruff
fixture mutation failed with `ResolutionImpossible` in 3.342 seconds, and
exact restoration passed in 4.421 seconds. The owning checkout had no diff
against HEAD after restoration.

GitHub marked both Autofix jobs flagged in round 2 as canceled with no
executed steps ([run 42929978596](https://github.com/stranske/trip-planner/actions/runs/42929978596)).
The later run at the same head succeeded, with Resolve Context passing and
dispatch completion skipped ([run 42929979836](https://github.com/stranske/trip-planner/actions/runs/42929979836)).

This seat has read-only access to `.agents`. `ledger-reconciliation.patch` is
an **unapplied proposal**, not current ledger state. It reconciles tasks 05 and
14, records the owning commit and exact commands/outcomes, documents regression
coverage and mutation evidence, and records the subsequent sync classification.
Task 05 is deferred because the proposed pin/publication fix was superseded;
the proposed task 14 records the passing smoke and documented local check.
Source integration into Workflows main and the actual ledger write remain
outstanding.

## Keepalive round 3 readback

The two named run logs and final-head smoke JSON were fetched again. The owning
checkout remains clean at `f1ae1a4b8f704bf147938880c0010ded18d51022`. The focused
resolver command passed all eight tests in 4.85 seconds; the exact documented
local command above exited 0 again. See `round-3-dev-check.log` and
`round-3-readback.json` for the checked time, commands and commit. Existing
mutation/restoration receipts remain unchanged. No dependency pins were edited.

A fresh read of canonical sync-core round `20261108T133016Z` again identifies
#2006 as delivered, with zero mismatches and no dependency-pin finding in its
reasons or handoffs. The workflow report artifact path was independently
rechecked in Maint 68 at the owning commit.

T1, T3 and T4 remain incomplete because each requires writing the actual
`.agents/issue-2007-ledger.yml`, which this execution seat explicitly makes
read-only. A2 likewise remains incomplete despite the passing command. The
existing reconciliation patch is still an unapplied proposal. An authorized
writer with access to the ledger must apply and verify it; changing the path
or bypassing the restriction would not resolve the access boundary.
