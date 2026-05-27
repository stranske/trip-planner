## 2026-05-27T02:55Z - opener lane issue #1235 materializing

- Repo: `stranske/trip-planner`
- Issue: `#1235` (`Add fuzzy/deterministic matching layer for planner notebook focus and reorientation`)
- Branch: `codex/issue-1235-notebook-focus-matching`
- Lane: opener / codex
- Status: implementation complete locally; preparing push and ready-for-review PR.
- Selection notes:
  - Required cap-health reported `total_opener_owned=0`, `raw_cap_reached=false`, `non_drainable_count=0`.
  - `opener-repair-infra-stalls.py` made no repairs.
  - Priority discovery found LMS `#121` high priority but it is the final M6 gate and explicitly sequenced after individual M5/M6 surfaces.
  - Approved queue contained this high-priority trip-planner item and no matching open issue/PR existed, so opener materialized remote issue `#1235`.
  - Canonical Code-root checkout was behind and had an unrelated `.gitignore` modification; implementation was isolated in this automation-owned clone at `/Users/teacher/.codex/automations/pd-workloop-resume/worktrees/trip-planner-issue-1235`.
- Implementation:
  - Added `_match_notebook_category` with shared synonym matching for lodging, route, activities, budget, documents, and policy terms.
  - Replaced exact keyword focus matching with the synonym matcher for phrases such as hotel/stay and flight/train focus turns.
  - Added a structured clarification path for ambiguous later/future-list notebook references.
  - Updated `docs/design-coverage-map.md` LangChain Planner Runtime memory row to mark notebook reorientation implemented.
- Validation:
  - `pytest tests/app/test_planner_routes.py::test_planner_turn_handles_planning_notebook_commands tests/app/test_planner_routes.py::test_planner_turn_matches_notebook_focus_synonyms_and_clarifies_ambiguity -q` -> 2 passed.
  - `pytest tests/app/test_planner_routes.py -q` -> 34 passed.
  - `make full-product-check` -> command exited 0; `local-leisure-journey PASS`, `local-business-journey PASS`; frontend runtime, map provider, and live TPP skipped due missing local deps/env.
  - `python -m ruff check trip_planner/app/services/planner.py tests/app/test_planner_routes.py` -> passed.
  - `python -m ruff format --check trip_planner/app/services/planner.py tests/app/test_planner_routes.py` -> passed after formatting.
  - `python -m mypy trip_planner/app/services/planner.py tests/app/test_planner_routes.py` -> passed.
- Next action: push branch, open ready-for-review PR, label `agent:codex`, `agents:keepalive`, and `autofix`, then emit `pr_opened`.

## 2026-05-24T05:28Z - opener lane issue #1208 PR opened

- Repo: `stranske/trip-planner`
- Issue: `#1208` (`Add LangSmith tracing for planner conversations and tool calls`)
- PR: `#1226` (`Issue #1208: Add planner LangSmith fleet traces`)
- Branch: `codex/issue-1208-langsmith-planner-traces`
- Lane: opener / codex
- Status: PR opened and handed to keepalive
- Labels verified on PR: `agent:codex`, `agents:keepalive`, `autofix`
- Branch state: pushed after PR handoff state update.
- Validation:
  - `python -m pytest tests/observability/test_langsmith_fleet.py tests/app/test_planner_routes.py -q --no-cov` -> passed, 37 tests.
  - `python -m ruff check trip_planner/observability/langsmith_fleet.py trip_planner/app/services/planner.py tests/observability/test_langsmith_fleet.py tests/app/test_planner_routes.py` -> passed.
  - `python -m mypy trip_planner/observability/langsmith_fleet.py trip_planner/app/services/planner.py` -> passed.
  - `git diff --check` -> passed.
- Relay: `pr_opened active.source_repo=stranske/trip-planner active.source_issue=1208 active.source_pr=1226 active.next_action=wait_for_keepalive`.
- Next action: keepalive owns PR `#1226`; do not wait for CI inside opener.

## 2026-05-24T05:20Z - opener lane issue #1208 PR materializing

- Repo: `stranske/trip-planner`
- Issue: `#1208` (`Add LangSmith tracing for planner conversations and tool calls`)
- Branch: `codex/issue-1208-langsmith-planner-traces`
- Lane: opener / codex
- PR: `#1226` (https://github.com/stranske/trip-planner/pull/1226)
- Status: PR opened, non-draft, labeled `agent:codex`, `agents:keepalive`, and `autofix`
- Notes:
  - Selected from supported-repo existing LangSmith child issues after priority searches returned no eligible implementation issues and cap-health reported raw opener cap below 5.
  - Reused the existing mid-materialization worktree for this issue; no open PR existed for the branch at selection time.
  - Local main worktree had an unrelated `.gitignore` edit, so all issue work is isolated in this worktree.
- Validation:
  - `python -m pytest tests/observability/test_langsmith_fleet.py tests/app/test_planner_routes.py -q --no-cov` -> 37 passed, 33 warnings.
  - `python -m ruff check trip_planner/observability trip_planner/app/services/planner.py tests/observability/test_langsmith_fleet.py tests/app/test_planner_routes.py` -> passed.
  - `python -m mypy trip_planner/observability trip_planner/app/services/planner.py` -> passed.
  - `git diff --check` -> passed.
- Relay: emitted `issue_created` for source issue `#1208` and `pr_opened` for source PR `#1226`.
- Next action: keepalive owns PR `#1226`; opener should move to the next eligible issue on a future round after cap checks.
