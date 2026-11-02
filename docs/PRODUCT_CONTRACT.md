# Product contract — stranske/trip-planner
_First draft generated 2026-09-20 from the audit scorecard; the repo owns this file from now on. A PR that adds a user-facing route, command or page adds a line here. The audit's Phase 1.5 scores every line below and prints any surface not listed as UNSCORED._

## Purpose
Enable a business traveller to plan a trip and hand it to Travel-Plan-Permission for policy approval and travel documents.

## Primary journey
Sign up → create business trip → compare options → message planner → check policy → submit proposal → print/export approval packet.

## Core functions

The **status** column tracks the latest offline `product-probe.json` from
`python scripts/check_full_product_verification.py --live-tpp off --contract-report product-probe.json`
(commit on `main` when the doc was last refreshed). The offline probe uses real
application routes with local TPP fixture envelopes. **TP7 stays PARTIAL** until
browser print/export is observed: `_probe_packet` only proves backend packet
readiness (`scripts/check_full_product_verification.py`), not a real print dialog.

| id | a user can … and sees … | entry point | probe (how to exercise it; vary these determinants) | status (product-probe.json, latest main run) |
|---|---|---|---|---|
| TP1 | a traveller can sign up or sign in and sees a session that survives navigation | `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/session` | vary fresh signup and existing-account login; navigate/create request then read session | WORKS |
| TP2 | a traveller can create a business trip and sees persisted destination, dates, party and purpose | `/trips/new` → `POST /api/trips` | POST trips with different destination, dates, party and purpose; read each trip | WORKS |
| TP3 | a traveller can compare scenarios and sees ranked cost, travel time, transfers and feasibility for the trip | Compare tab → `GET /api/workspace/{id}/scenarios/compare` | compare Reykjavik vs Nairobi, party 1 vs 8, duration 1 vs 14 days; diff figures. Contract probes include an origin (Seattle) so destination changes exercise inter-city travel determinants. | PARTIAL |
| TP4 | a traveller can message the planner and sees a reply responsive to the request | Plan tab → `POST /api/planner/{id}/turns` | vary cancellation and gibberish; assert cancellation acknowledgement versus fallback reply | PARTIAL |
| TP5 | a traveller can check policy and sees a policy snapshot and posture for the trip | Policy tab → `PUT /api/workspace/{id}/policy` | vary policy payload fare/cabin limits; inspect resulting state and blockers | WORKS |
| TP6 | a traveller can submit for approval and sees a TPP proposal execution | Policy tab Submit → `PUT /api/workspace/{id}/proposal` | vary proposal home_airport and policy context; inspect execution/error | WORKS |
| TP7 | a traveller can print or export an approval packet and sees a printable approver document | Policy tab Print / Export (`ApprovalPacket`) | submit then open ApprovalPacket and print/export | PARTIAL |

## Known gaps (aligned with latest `product-probe.json`)
- TP3: compare still reports **PARTIAL** when scenario figures do not yet move on every documented determinant (destination/party/duration); see `_probe_comparison` in `scripts/check_full_product_verification.py`.
- TP4: planner replies remain **PARTIAL** on deterministic fallback without a configured LLM provider (distinct replies, not byte-identical — see issue #1742).
- TP5–TP6: contract probes now **WORKS** end-to-end (policy sync via `frontend/src/api/workspace.ts` and proposal execution in `scripts/check_full_product_verification.py`); remaining product risk is live TPP/hosted behaviour, not missing frontend wiring.
- TP7: backend packet readiness passes, but **PARTIAL** until a browser print/export observation is recorded (see `_probe_packet`).
