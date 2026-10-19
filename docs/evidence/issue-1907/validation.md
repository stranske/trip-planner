# Executed transition audit validation

Source main: `3d4cafc6a830849ed5435f8a5b04181545ae648a`. All observations below are local and offline.
Interpreter: repository-selected `.venv/bin/python` (CPython 3.14), explicitly invoked
at `/Users/teacher/Library/CloudStorage/Dropbox/Learning/Code/trip-planner/.venv/bin/python`.

- `python -m pytest tests/app/test_proposal.py -q`: **99 passed**. Nonempty
  collection includes both new audit regressions; `restored-proposal.txt`.
- `python -m pytest tests/app/test_proposal_payload_truth.py tests/integrations/test_canonical_state_seam.py tests/app/test_planner_turn_e2e.py -q`:
  **15 passed** (parametrization included); `adjacent-python.txt`.
- In frontend, `./node_modules/.bin/vitest run src/components/maps/TripMap.test.tsx src/components/maps/mapSurface.test.ts`:
  **26 passed**, 2 files, Vitest 4.1.10; `maps.txt`.
- `python -m mypy tests/app/test_proposal.py`: **PASS**; `mypy.txt`.
- `python -m ruff check tests/app/test_proposal.py`, Black check and `git diff --check`:
  **PASS** after formatting.

## Actual disconnections

Both mutations changed `trip_planner/app/services/proposal.py` temporarily and
ran `python -m pytest tests/app/test_proposal.py::test_transition_audit_native_submit_preserves_lineage_at_each_consumer -q`.

1. Replace native builder assignment `proposal_payload["source_version"] = source_version`
   with removal: **1 failed**, `AssertionError: native builder lineage lost before persistence`.
   The storage resolver remains intact, so this demonstrates that downstream repair
   cannot mask the missing producer field. `builder-lineage-disconnected.txt`.
2. Replace storage assignment `stored_proposal_payload["source_version"] = source_version`
   with removal: **1 failed**, storage assertion `KeyError: 'source_version'`.
   `storage-lineage-disconnected.txt`.

After each mutation the original source bytes were restored and SHA-256 checked.
The complete restored 99-test proposal suite passed. `disconnection-receipt.json`
contains replacements, exits, timestamp, interpreter and restored source hash.
The later inventory-completeness assertion was rerun before publication.
Production source is unchanged in the PR; no fixture verdict, live SDK request,
hosted-service, deployment, separate OS process or original verifier acceptance
is inferred from these results. No new production defect was confirmed.
