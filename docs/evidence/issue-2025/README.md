# Issue 2025 acceptance evidence

Checked 2026-11-11T00:09:25.637118+00:00. Three of four acceptance criteria have positive
local evidence. **The documented local command fails. This is incomplete.**

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

## Incomplete acceptance and ledger reconciliation

At the linked Workflows commit:

```sh
TMPDIR=/private/tmp PATH="/tmp/trip-2025-workflows/.venv/bin:$PATH" ./scripts/dev_check.sh
```

Exit 1. The first broken step is `mktemp` for the syntax check: it still tries
the protected macOS default temporary directory and reports `Operation not
permitted`. Earlier environment attempts exposed an unrelated plugin and a
missing PyYAML dependency. The declared stop rule was three repair attempts or
60 minutes; repairs stopped at the attempt limit. `owner-dev-check.log` is the
final output. No comprehensive local suite was run.

This seat has read-only access to `.agents`. `ledger-reconciliation.patch` is
an **unapplied proposal**, not current ledger state. It reconciles tasks 05 and
14, records the owning commit and exact commands/outcomes, documents regression
coverage and mutation evidence, and records the subsequent sync classification.
Task 05 is deferred because the proposed pin/publication fix was superseded;
task 14 remains blocked by the failed documented command. Other historical
ledger entries are preserved. Source integration into Workflows main, the
actual ledger write and successful documented validation remain outstanding.
