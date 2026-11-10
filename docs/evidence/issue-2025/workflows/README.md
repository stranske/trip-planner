Workflows resolver regression, checked 2026-11-10

The implementation belongs in `stranske/Workflows`. This directory exports its
five new test/fixture files for review because upstream publication was denied.
It is not a second consumer test suite. The sibling `workflows-regression.patch`
contains the same files as Workflows commit
`2a1605a42fa5767ece7020a2f375e9a15cdf5e48`, based on
`1ff1a3c5071824adc2fd421702f583b14dc6b477`. Apply that patch in an authorized
Workflows checkout with `git am /path/to/workflows-regression.patch`.
No workflow, pin, synced consumer file or sync manifest changes are included.

Editable-install follow-up, 2026-11-10: apply
`../workflows-editable-resolution.patch` after `workflows-tool-mutations.patch`.
Both historical checkout tests now also ask pip to prepare two local editable
projects with dev extras. The passing report must identify both projects as
editable directories. The stdlib-only fixture backend exports the same three
tool requirements as the wheel tests; it does not build either product or
resolve runtime dependencies. The suite makes twelve pip calls with eight-second
deadlines. In the reconstructed owning source, all **8 tests pass in 5.59s**;
changing successful TPP Ruff back to 0.17.2 fails the editable positive case,
and restoring it passes. `../owner-editable-verification.json` records the
command, source hashes and mutation results. Upstream publication and the
documented broad local validation remain blocked.

Follow-up on 2026-11-10: apply `../workflows-tool-mutations.patch` with `git apply`
after the original patch. Together they reproduce the exported test source,
including its earlier type annotation correction. Three new parameterized cases
restore each historical producer Ruff, mypy or pytest pin independently, require
pip to name that exact conflict, then restore the successful metadata and require
resolution. Ruff can otherwise mask the other two conflicting pins. Each pip
subprocess now has a ten-second deadline (ten invocations in the whole suite).

The expanded suite passed with **6 tests in 4.32 seconds** in an offline sparse
source reconstruction of Workflows base
`8c678c19a4f9f60fa5be6a00f08794a9626c87bd`. The source configuration, production
sync module and test support match nine immutable Git blob hashes recorded in
`../owner-tool-mutations.json`; it also records the tested source hash and exact
command. `../owner-tool-mutations-pytest.log` retains the result. The original
Ruff mutation still fails and restoring it passes; the corresponding follow-up
logs retain both results. The new tests remain unpublished in Workflows.

`tests/test_dependency_resolution.py` runs pip offline with metadata-only wheels
for the two projects' dev extras and Ruff, mypy and pytest. Fixtures preserve the
dependency sections at the exact checkout commits in failed run 42449207754 and
successful run 42484305260; each fixture names its source URL. This bounds the
reported resolver regression, rather than testing full installation or builds.
The third test calls the existing `parse_env_file` and `sync_pyproject` functions
against the actual canonical `.github/workflows/autofix-versions.env`, whose
current Ruff pin is 0.17.4. It checks that propagating only the planner pins still
fails, whereas propagating both consumers resolves. The historical successful
fixtures retain Ruff 0.17.3 independently of later source updates.

Verified in a sparse Workflows checkout at `/tmp/issue2025-workflows` containing
the original project configuration, conftest, diagnostic fixture support and
production sync module. Their fetched Git blob hashes match the base commit.
The selected offline Python 3.14.10 venv exposes the preinstalled pytest 9.2.0,
pip 26.3, packaging and pytest's dependencies through package symlinks. It has
no unrelated third-party pytest plugins. No tests or warning checks were disabled.
The inherited consumer environment failed Workflows' strict warning policy at
startup because its AnyIO plugin is older than Workflows requires.

From the Workflows checkout:

```sh
/tmp/issue2025-resolver-env/bin/python -m pytest tests/test_dependency_resolution.py -m 'not slow' -q
```

Exit 0, three tests pass in 1.25 seconds on the committed source; the retained
`owner-pytest.log` records a later identical command's result. Each pip subprocess
has a 15-second timeout. Mutation changed only Ruff in the successful producer
fixture from 0.17.3 to 0.17.2. The successful-checkouts test failed with
`ResolutionImpossible` (exit 1, 0.69 seconds wall); restoring the original bytes
passed (exit 0, 0.68 seconds wall). See `mutation.log` and `restored.log`.
Terminal logs have trailing whitespace removed for repository formatting checks.

The README's documented `./scripts/dev_check.sh` was also attempted on that
commit, with `PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_RETRIES=0` because
shell network access is restricted. It exits 1 while provisioning unavailable
isort/docformatter/flake8 packages. This is not successful broad validation.
`owner-dev-check.log` retains the failure. The requested ledger is mounted
read-only; proposed reconciliation remains in `dependency-resolution.json`.

The Workflows branch creation, `needs-human` label and blocker comment each
received `MCP tool call requires approval, but approval policy is never`.
No upstream branch or PR was created. Source publication, the documented-command
exit-0 criterion and the ledger edits remain incomplete. PR #2026 readback was
open with draft=false. These artifacts do not claim all acceptance criteria pass.
