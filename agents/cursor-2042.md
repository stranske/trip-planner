<!-- bootstrap for cursor on issue #2042 run:44009357734-1 -->

## Verification: deliberate break → revert

With `if currency != "USD": return []` restored at `_budget_violations` line 59:

- `pytest tests/app/test_scenario_policy_preview.py::test_non_usd_total_with_usd_caps_is_preview_incomplete -q` → **2 failed** (BUD-001 missing from violations when EUR totals meet USD caps)

After reverting to `currency_uncheckable` incomplete findings:

- Same command → **2 passed**
- `pytest tests/app/test_scenario_policy_preview.py -q` → **68 passed**