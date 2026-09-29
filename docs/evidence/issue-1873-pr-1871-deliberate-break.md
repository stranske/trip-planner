# Issue #1873: PR #1871 deliberate-break evidence

This record closes the missing falsification evidence identified after PR #1871
merged as `2ae669c6d0b39a9e1d7524041dc473507630a7d3`. The final branch changes only
this evidence document; the production workflow and its contract test are restored
exactly to `origin/main`.

## Environment

```text
Python 3.12.2
pytest 9.1.1
PYTEST_ADDOPTS=<unset>
```

## Baseline

Command:

```bash
python -m pytest --no-cov tests/test_gate_commit_status_fork_tolerance.py -q
```

Literal output (exit 0):

```text
.............                                                            [100%]
13 passed in 0.61s
```

## Deliberate break (RED)

The sole deliberate mutation forced the fork-token classification off while
leaving every other condition unchanged:

```diff
               const readOnlyForkToken =
+                false &&
                 error?.status === 403 && isForkPullRequest && !hitRateLimit;
```

Command:

```bash
python -m pytest --no-cov tests/test_gate_commit_status_fork_tolerance.py -q
```

Literal output (exit 1):

```text
FFFFFF.......                                                            [100%]
=================================== FAILURES ===================================
________________ test_fork_read_only_403_does_not_fail_the_gate ________________

    def test_fork_read_only_403_does_not_fail_the_gate(outcomes: dict[str, Any]) -> None:
>       assert outcomes["fork_read_only"]["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:225: AssertionError
_______________ test_fork_read_only_403_reports_the_real_verdict _______________

    def test_fork_read_only_403_reports_the_real_verdict(outcomes: dict[str, Any]) -> None:
        case = outcomes["fork_read_only"]
        warning = " ".join(case["warnings"])
        summary = " ".join(case["summaryRaw"])
>       assert "read-only" in warning
E       AssertionError: assert 'read-only' in ''

tests/test_gate_commit_status_fork_tolerance.py:233: AssertionError
______________ test_fork_read_only_403_preserves_failure_verdict _______________

    def test_fork_read_only_403_preserves_failure_verdict(
        outcomes: dict[str, Any],
    ) -> None:
        case = outcomes["fork_read_only_failure"]
        warning = " ".join(case["warnings"])
        summary = " ".join(case["summaryRaw"])
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:247: AssertionError
__ test_fork_read_only_403_fails_closed_for_other_non_success_verdicts[error] __

    @pytest.mark.parametrize("state", ["error", "pending"])
    def test_fork_read_only_403_fails_closed_for_other_non_success_verdicts(
        outcomes: dict[str, Any], state: str
    ) -> None:
        case = outcomes[f"fork_read_only_{state}"]
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:259: AssertionError
_ test_fork_read_only_403_fails_closed_for_other_non_success_verdicts[pending] _

    @pytest.mark.parametrize("state", ["error", "pending"])
    def test_fork_read_only_403_fails_closed_for_other_non_success_verdicts(
        outcomes: dict[str, Any], state: str
    ) -> None:
        case = outcomes[f"fork_read_only_{state}"]
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:259: AssertionError
_____________ test_deleted_fork_read_only_403_reports_the_verdict ______________

    def test_deleted_fork_read_only_403_reports_the_verdict(
        outcomes: dict[str, Any],
    ) -> None:
        case = outcomes["deleted_fork_read_only"]
        warning = " ".join(case["warnings"])
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:269: AssertionError
=========================== short test summary info ============================
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_does_not_fail_the_gate
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_reports_the_real_verdict
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_preserves_failure_verdict
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_fails_closed_for_other_non_success_verdicts[error]
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_fails_closed_for_other_non_success_verdicts[pending]
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_deleted_fork_read_only_403_reports_the_verdict
6 failed, 7 passed in 0.51s
```

The failures cover ordinary fork success/failure/error/pending verdicts and the
deleted-fork case, demonstrating that the test suite observes the fallback rather
than merely exercising unrelated workflow text.

## Exact restoration (GREEN)

The added `false &&` line was removed with the inverse patch. Command:

```bash
python -m pytest --no-cov tests/test_gate_commit_status_fork_tolerance.py -q
```

Literal output (exit 0):

```text
.............                                                            [100%]
13 passed in 0.46s
```

## Restoration and PR-range hygiene

Commands:

```bash
git diff --exit-code origin/main -- .github/workflows/pr-00-gate.yml tests/test_gate_commit_status_fork_tolerance.py
git diff --check origin/main...HEAD
```

Both commands produced no output and exited 0 after the evidence commit. The first
proves the production workflow and test contract match `origin/main`; the second
proves the PR range has no whitespace errors.
