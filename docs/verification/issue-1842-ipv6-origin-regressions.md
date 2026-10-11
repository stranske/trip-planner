# Issue 1842: bracketed IPv6 handoff origin regressions

This round advances verification of the first task's fixed-origin browser POST.
Sixteen new regression cases cover malformed bracketed IPv6 authorities through
both configured destination settings, valid HTTPS IPv6 destinations, route
rejection without changing the saved verdict, and successful configuration
recovery. Supported Python 3.12 and 3.14 already reject the malformed authorities;
production code is unchanged. No task checkbox is marked complete.

Validation: 395 focused tests passed across the handoff integration, saved handoff,
proposal route, handoff flow and response-schema tests, with `-m 'not slow'`.
Relevant-file Black formatting and the required repository-wide Black check at
line length 100 passed (481 files unchanged). Mypy passed for both changed test
files. Ruff passes for the integration test and retains the same pre-existing
PYI034 finding in the proposal test as HEAD. `git diff --check` passed.
HTTP tests and Black used a temporary selector wait cap outside the repository
because the sandbox blocks asyncio socket wakeups; assertions were unchanged.

Frontend installation failed because the offline npm cache lacks `xmlchars`.
The real TPP portal contract skipped because `TPP_REPO_PATH` is absent.
Authenticated correlated status integration, the accepted pinned producer
contract, hosted checks and exact-head review gates remain outstanding.

Shared-checkout staging failed because `.git` is read-only. The source commit is
preserved in `/tmp/trip-planner-ipv6-commit`, with an apply-ready patch and bundle at
`/tmp/trip-planner-ipv6-handoff.patch` and `/tmp/trip-planner-ipv6-handoff.bundle`.
The changed files remain in the working tree for automation pickup. An owning
writable lane must apply and publish the commit.

Automatic approval review rejected the requested blocker comment and
`needs-human` label because GitHub mutations require approval while this run's
policy is `never`; neither was applied. PR #1872 was observed open and ready for
review at its original head.
