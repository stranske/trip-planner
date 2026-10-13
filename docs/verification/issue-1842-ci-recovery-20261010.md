# PR1872 repeated CI recovery

Starting head: `7baa9f3f3dd74dadb26d67858a3f80015d13c0f1`.
Hosted Gate `38074600476` failed before product pytest: dependency declaration preflight required the directly imported pydantic package; mypy rejected the nested submission_error value added to a fixture annotated dict[str, str]. Earlier lane prose calling this os.environ.update was incorrect: it is live.update at line479.

The business fixture now returns dict[str, object], matching its mixed-value JSON shape without disabling checks. Dev dependencies declare the already-resolved pydantic2.13.4; uv regenerated requirements.lock with the existing no-emit-package app-baseline-kit policy. No package version changed. The dependency verifier succeeds without invoking the tomlkit-dependent auto-fix fallback.

Validation with the retained private Python3.12.2 overlay:
- Exact hosted mypy command `python -m mypy --config-file pyproject.toml --exclude .workflows-lib .`: before exit1, one error in443 source files; after exit0, no issues in443 files.
- `python scripts/sync_test_dependencies.py --verify`: exit0, all imported test dependencies declared.
- `python -m pytest tests/scripts/test_check_full_product_verification.py tests/integration/test_portal_contract_checkout.py tests/integrations/test_tpp_portal_handoff.py -q`:153passed.
- Black and git diff --check pass.

Raw before/after consoles and JUnit are retained in the closer automation work/20261010T1822Z directory. Hosted Linux CI remains required; this does not establish full product acceptance. Valid active review finding4174712854 and source1842 authenticated correlated receipt/status integration remain open, dependent on accepted Travel-Plan-Permission1659. No merge or verifier PASS is claimed.
