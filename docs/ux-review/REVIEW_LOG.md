# UX Review Log — trip-planner

Diff-anchored record of UX Review (`/ux-review`) passes. Detailed artifacts live in `Orchestrator/ux_reviews/`.

## 2026-06-22 — Vite SPA + FastAPI (synthetic demo seed) — commit `3e25681` — overall 7.0/10 (gate PASS)

- **Scope:** full-stack local (Vite `:5173` + FastAPI `:8000` on SQLite), the repo's documented synthetic demo seed (`TRIP_PLANNER_SEED_DEMO`, `demo@trip-planner.local`). Also serves as Travel-Plan-Permission's UI.
- **Coverage:** login ✓; Saved Trips list ✓; Workspace ✓; Plan / Compare / Map / Budget tabs ✓; scenario comparison ✓ (3 routes with time/transfers/cost). NOT driven: Notebook / Policy tabs, signup, create-trip.
- **Scores:** wired 6.5 / usability 7.0 / help_clarity 7.0 / workflow 7.5 — **PASS**. The most fully-functional app in the fleet (completes login → trips → workspace → scenario comparison end-to-end, well-guided with NEXT-ACTION + approval-readiness).
- **Findings → filed:**
  - Header stays logged-out after login — root loader `session` not revalidated (`frontend/src/App.tsx:40`, gating at `:63-83`) → **#1448**.
  - Map tab shows no visual map, only a text "approximate sketch" (`frontend/src/components/maps/TripMap.tsx:176`, `mapSurface.ts:809`; README-acknowledged follow-on) → **#1449**.
- **Next focus:** drive Notebook / Policy tabs + signup + create-trip; revisit Map once a provider is wired.
