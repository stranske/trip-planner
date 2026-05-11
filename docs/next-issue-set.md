# Next Issue Set

This note captures the remaining gaps after the recent readiness, planner-runtime, notebook, planning-mode, map, and workspace-polish work. It is intentionally issue-shaped so the next round can be opened as focused GitHub issues instead of bundled into one broad cleanup PR.

## 1. Add Planner Model Routing Policy

**Goal:** Route quick traveler turns to a low-latency model path and route synthesis, comparison, and major planning updates to a deeper model path.

**Why it matters:** The UI now exposes planning modes, but runtime model choice is still mostly configuration-level. A product planner needs fast acknowledgement for simple turns and visibly more careful reasoning when the traveler asks for route comparison, tradeoff synthesis, or a durable plan update.

**Scope:**

- Add a backend policy that classifies planner turns by task type, selected planning mode, and requested action.
- Preserve deterministic fallback behavior when no provider is configured.
- Persist model-routing metadata on planner turns so the UI and tests can distinguish quick turns from deeper planning turns without exposing developer language to travelers.
- Add fake-model tests for low-latency and deeper-routing branches.

**Acceptance criteria:**

- Simple acknowledgement, note capture, and notebook-focus turns use the fast path.
- route comparison, final summary, major itinerary revision, policy submission preparation, and "think this through" prompts use the deeper path.
- The planner response records route/model-class metadata in a developer-facing payload while hiding it from normal traveler copy.
- Tests prove routing is mode-aware and provider-free in CI.

## 2. Build Semantic Planner Memory And Reorientation

**Goal:** Let a traveler scatter notes during planning and later say "I was working on lodging in Oslo" or "put this in the future list" and have the planner and UI reorient to the right planning file.

**Why it matters:** Planning is non-linear. The current notebook tools can capture, focus, read, and complete items, but the system still needs a stronger memory layer for category inference, ambiguous references, and UI reorientation.

**Scope:**

- Add structured memory categories for lodging, transport, activities, budget, route options, policy, documents, and future questions.
- Add semantic matching or deterministic fallback matching from traveler phrasing to notebook items/categories.
- Expose focused memory state in the workspace so the relevant list, route option, or planning panel becomes active without menu-clicking.
- Add completed-item history for major planning categories.

**Acceptance criteria:**

- "Remember this for hotels" creates or updates a lodging notebook item.
- "I was working on the Oslo stay" focuses the matching lodging item and returns nearby open/completed items.
- Completed items remain visible in completed-history views and can be reopened.
- Ambiguous references prompt a user-friendly clarification instead of silently filing the note incorrectly.

## 3. Expand Provider-Rich Planner Tools

**Goal:** Move beyond first-pass app-state tools by exposing source retrieval, route/map provider checks, source-quality scoring, and route comparison refresh as planner-callable tools.

**Why it matters:** `planner_tools.py` is now real, but the model cannot yet request richer source or provider work. This limits how much the planner can revise a route based on fresh information.

**Status:** Implemented for provider-rich tool seams. The planner can now call bounded source-summary, map-provider-status, route-geometry, and deterministic route-comparison refresh tools. Source-quality scoring remains a separate executable-engine gap; the planner tool returns an explicit `not_available` result until that service exists.

**Scope:**

- Add read-only tools for source retrieval and source-quality summaries.
- Add route/map provider-status and route-geometry tools that consume existing map-surface and runtime scenario contracts.
- Add route-comparison refresh tools that update scenario rankings without bypassing existing deterministic services.
- Keep tool outputs bounded, referenced, and persisted in planner traces.

**Acceptance criteria:**

- The planner can request route options, source-quality notes, and map-provider status through named tools.
- Unsupported provider states return visible bounded errors, not fabricated success.
- Tool traces remain persisted and testable through planner routes.

## 4. Verify Live TPP Integration End To End

**Goal:** Run the trip-planner to Travel-Plan-Permission round trip against a live or sibling TPP service and record the required setup.

**Why it matters:** Contract and seam tests pass, but default readiness still skips live TPP when `TPP_BASE_URL` or `TPP_REPO_PATH` is absent. Release confidence needs at least one documented live verification lane.

**Scope:**

- Confirm local sibling startup through `TPP_REPO_PATH`.
- Confirm remote startup through `TPP_BASE_URL`, `TPP_ACCESS_TOKEN`, and `TPP_OIDC_PROVIDER`.
- Add or update docs for expected env vars, failure modes, and captured logs.
- Record whether the current deployed Render/Netlify setup can exercise the business policy flow without local developer commands.

**Acceptance criteria:**

- `make full-product-check` reports live TPP readiness, not `SKIPPED`, in at least one configured environment.
- Failures include actionable service command, env var, and recent log context.
- The traveler-facing UI keeps policy failure details understandable without developer jargon.

**Status (2026-05-11, issue #1161):** Code-side scaffolding for diagnostics and mode-safety is in place. The verifier now emits a `remediation` hint on every non-PASS `live-tpp` result, distinguishes `invalid_path` kinds (`missing` vs `not-a-directory`), and is regression-pinned so `TPP_BASE_URL` mode never resolves a sibling interpreter. The two configured transport modes are documented in [`docs/local-testing-plan.md` → "Live TPP Verification Setup"](local-testing-plan.md#live-tpp-verification-setup) and cross-linked from [`docs/live-tpp-execution-reoptimization-epic.md`](live-tpp-execution-reoptimization-epic.md#local-verification-setup). The remaining gap is exercising one configured environment so `make full-product-check` reports `live-tpp PASS` instead of `SKIPPED`; that requires either a sibling `Travel-Plan-Permission` checkout with a working `.venv`/`uv` setup or an externally hosted preview, neither of which is exercised by the default CI matrix yet.

## 5. Deepen Map, Route, And Timeline Presentation

**Goal:** Make map/timeline surfaces support a coherent global, regional, and local review flow.

**Why it matters:** The current map and timeline are usable and tested, but they still rely on shaped route summaries. Travelers need a rough whole-trip outline plus precise segment review for specific decisions.

**Status (2026-05-11, issue #1162):** Implemented for the shared review-state and segment timing seam. Map scope now covers whole-trip, regional route, and segment-level review; selected route and segment state drive the map, day-plan timeline, scenario comparison, and planner route-focus panel. Runtime map geometry now carries duration/confidence/unavailable-state detail per segment. Remaining work is live provider distance/geometry verification and deeper source-backed marker detail.

**Scope:**

- Strengthen the map scope model from global/local into global, regional, and segment-level views.
- Carry selected route option and selected segment state across map, timeline, scenario comparison, and planner conversation.
- Add provider-rich per-leg timing/distance when available and keep graceful fallback when unavailable.
- Add UI states that explain confidence and precision in traveler language.

**Acceptance criteria:**

- Switching a route option updates map, timeline, scenario cards, and planner context together.
- Switching to a segment-level view highlights the relevant route leg, markers, notes, and open decisions.
- Missing provider geometry still leaves a useful schematic and comparison board.

## 6. Implement Source Quality Scoring

**Goal:** Turn `source-quality-model.md` and `source-channel-strategy.md` into executable scoring and explanation code.

**Why it matters:** The planner should not treat raw ratings, stale articles, review snippets, and official provider data as equivalent. Source confidence needs to influence ranking and traveler-facing explanations.

**Scope:**

- Add a source-quality engine that scores freshness, channel fit, provenance, conflict state, and traveler relevance.
- Wire source-quality signals into ranking explanations and planner source summaries.
- Add tests for stale, conflicting, official, crowd-review, and sparse-source scenarios.

**Acceptance criteria:**

- Candidate and route explanations include source-confidence language.
- Stale or conflicting inputs reduce confidence without deleting useful options.
- Source-quality behavior is deterministic and covered by tests.

**Status (2026-05-11):** The deterministic engine, conflict detection, and traveler-facing summary shape are implemented in `trip_planner/sources/quality.py` with `tests/sources/test_source_quality.py` and a ranking-explanation builder in `trip_planner/ranking/explanations.py` (`tests/ranking/test_source_confidence_explanation.py`). The remaining downstream work is to attach resolved `SourceRecord`/`ProvenanceReference` instances onto bundles so the `read_source_quality_summary` planner tool and the leisure/business engines can consume the engine end-to-end.

## 7. Finish Product UX Cleanup For Traveler Comfort

**Goal:** Remove remaining developer-shaped copy and make the workspace feel like a planning product rather than an implementation surface.

**Why it matters:** The app now hides several raw provider/debug labels, but the next pass should make traveler input formatting, planner reply formatting, help affordances, and route-option comparison feel intentional.

**Status (2026-05-11, issue #1164):** Implemented for the current workspace shell. The primary workspace now keeps raw IDs, tool traces, provider details, and debug payloads behind diagnostics; planner replies render in stable sections for next step, options considered, tradeoffs, saved notes, rejected options, open questions, decisions, and summaries; prompt chips cover note capture, decisions, checklist items, route comparisons, and follow-up summaries; route-option cards show tradeoff summaries for up to four options; and planning/map controls include traveler-friendly hover titles.

**Scope:**

- Add a compact, expandable "How to use this workspace" help section.
- Improve traveler input formatting for scattered notes, route comparisons, decisions, and checklist actions.
- Improve planner reply formatting with clear summaries, options considered, rejected options, next actions, and durable references.
- Keep a hidden developer-facing diagnostic trail for debugging.

**Acceptance criteria:**

- Normal workspace usage does not surface raw IDs, provider labels, tool names, or runtime terms.
- Planner replies consistently separate next step, options, tradeoffs, saved notes, and open questions.
- Hover/tooltips explain planning mode and map controls in traveler-friendly language.
