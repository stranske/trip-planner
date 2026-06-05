## 2026-06-05T21:09:59Z - opener (codex): issue #1318 daily menu PR ready

- Repo: stranske/trip-planner
- Issue: #1318, deterministic daily-activity-menu module
- Branch: codex/issue-1318-daily-menu
- Status: implementation complete locally; ready to push/open PR.
- Scope delivered:
  - Added `trip_planner/itinerary/daily_menu.py` with `MenuStop`, `SourceMix`, `MenuRollup`, `DailyMenu`, `SourceFeedbackBandit`, `calibrate`, and `build_daily_menu`.
  - Exported daily-menu contracts from `trip_planner.itinerary`.
  - Added `build_daily_menu` planner tool definition and handler, synthesizing compact menu digests from workspace activity bundles and source commerciality signals.
  - Added ported spike behavior tests and a planner tool registration/dispatch test.
- Validation:
  - `python -m pytest tests/itinerary/test_daily_menu.py -q` -> 6 passed.
  - `python -m pytest tests/app/test_planner_build_daily_menu_tool.py -q` -> 1 passed.
  - Deliberate-break calibration gate: zeroing the balance penalty made `test_slider_shifts_commercial_mix` fail with identical realized commercial mix `0.14 < 0.14`; restored and reran green.
  - Deliberate-break tool wiring gate: removing `"build_daily_menu": _build_daily_menu` made dispatch fail with `Planner tool 'build_daily_menu' is not supported`; restored and reran green.
  - `python -m ruff check trip_planner/itinerary/daily_menu.py trip_planner/itinerary/__init__.py trip_planner/app/services/planner_tools.py tests/itinerary/test_daily_menu.py tests/app/test_planner_build_daily_menu_tool.py` -> passed.
  - `python -m pytest tests/itinerary tests/app -q` -> 294 passed, 159 warnings.
  - `git diff --check` -> passed.
- Next action: open ready-for-review PR with `agent:codex`, `agents:keepalive`, `autofix`, and `agent:retry`; then hand off to keepalive.
