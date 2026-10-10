# Planner cross-repo smoke gate

The repo-owned `.github/workflows/cross-repo-smoke.yml` runs
`make full-product-check` with `TPP_REPO_PATH=../Travel-Plan-Permission` and
`LIVE_TPP=required`. `TPP_PINNED_REF` is the exact producer revision; bump it
only after the corresponding producer contract is accepted.

The portal contract test runs with `Travel-Plan-Permission/.venv/bin/python`.
That environment resolves both applications together: both TPP and trip-planner runtime
and dev/test extras. The previous branch pin was
`f2d5cfd4bd2ee31c5d632d502c8dae212f63a0a6`. This repair pins the current merged
producer `ac3bfb9f39e7a3144cbe19fd1894d333dfe93b75`, used in the real-app replay
and having compatible dev requirements. The producer-side paired pin follows
through existing producer #1658 after the final consumer revision is accepted. `pip check` must pass before the contract runs;
installation failure cannot fall back to a runtime-only environment. The
separate setup-python environment supports the planner full-product command;
the TPP service starts with the same private interpreter as the contract test.

This gate proves the existing portal preparation/submission contract. It does
not prove the authorized receipt/status return until TPP #1658 and consumer
#1842 integration are accepted. Keep #1842 open and preserve unknown manager
status/decision until authenticated correlated receipt evidence exists.

## CI recovery validation (2026-10-10)

The original hosted run 37423019366 failed importing SQLAlchemy in the TPP
private interpreter. An initial exploratory
replay incorrectly used the canonical checkout's stale `d7c5c31` producer pin,
which returned 404; that was not #1872's original `f2d5cfd` pin or its hosted
failure. The current producer replay then rejected
incomplete policy facts and near-departure dates with 409. The repaired test
provides synthetic traveler-owned fare/cabin evidence and travels 60 days in
the future, then exercises the real pinned producer's submission and manager
queue. No policy function is mocked or weakened. Planner manager status stays
unknown without an authenticated return receipt.

Validation with pinned TPP `ac3bfb9f39e7a3144cbe19fd1894d333dfe93b75`:
both projects' dev extras resolve together, the same private Python reports
`No broken requirements found`, and 161 affected tests pass. Removing the
planner dependency install from the actual workflow makes the named boundary
test fail; byte-identical restoration passes. Black, Ruff and whitespace
checks pass. Local Python is 3.12.2; the hosted workflow selects 3.14, so this
is focused local validation, not hosted parity or full-product-check PASS.
Raw install, failure, JUnit and mutation receipts are retained by the closer
in round `20261010T1634Z`. Hosted checks and full #1842 acceptance remain required.
