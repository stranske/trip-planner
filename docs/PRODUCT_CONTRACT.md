# Product contract — stranske/trip-planner
_First draft generated 2026-09-20 from the audit scorecard; the repo owns this file from now on. A PR that adds a user-facing route, command or page adds a line here. The audit's Phase 1.5 scores every line below and prints any surface not listed as UNSCORED._

## Purpose
Enable a business traveller to plan a trip and hand it to Travel-Plan-Permission for policy approval and travel documents.

## Primary journey
Sign up → create business trip → compare options → message planner → check policy → submit proposal → print/export approval packet.

## Core functions
| id | a user can … and sees … | entry point | probe (how to exercise it; vary these determinants) | status 2026-09-20 |
|---|---|---|---|---|
| TP1 | a traveller can sign up or sign in and sees a session that survives navigation | `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/session` | vary fresh signup and existing-account login; navigate/create request then read session | WORKS |
| TP2 | a traveller can create a business trip and sees persisted destination, dates, party and purpose | `/trips/new` → `POST /api/trips` | POST trips with different destination, dates, party and purpose; read each trip | WORKS |
| TP3 | a traveller can compare scenarios and sees ranked cost, travel time, transfers and feasibility for the trip | Compare tab → `GET /api/workspace/{id}/scenarios/compare` | compare Reykjavik vs Nairobi, party 1 vs 8, duration 1 vs 14 days; diff figures | FABRICATED |
| TP4 | a traveller can message the planner and sees a reply responsive to the request | Plan tab → `POST /api/planner/{id}/turns` | vary cancellation and gibberish; assert cancellation acknowledgement versus fallback reply | PARTIAL |
| TP5 | a traveller can check policy and sees a policy snapshot and posture for the trip | Policy tab → `PUT /api/workspace/{id}/policy` | vary policy payload fare/cabin limits; inspect resulting state and blockers | BROKEN |
| TP6 | a traveller can submit for approval and sees a TPP proposal execution | Policy tab Submit → `PUT /api/workspace/{id}/proposal` | vary proposal home_airport and policy context; inspect execution/error | BROKEN |
| TP7 | a traveller can print or export an approval packet and sees a printable approver document | Policy tab Print / Export (`ApprovalPacket`) | submit then open ApprovalPacket and print/export | BROKEN |

## Known gaps at draft time
- TP3: destination and party size do not change scenario figures; cost is duration-only and feasibility is constant.
- TP4: replies differ by message but remain deterministic fallback with no provider (issue #1742 addressed byte-identical replies only).
- TP5: no frontend call reaches the policy route, leaving `policy_state` null and no actionable blockers.
- TP6: submission is blocked by null policy context; a populated payload still fails because it omits required `home_airport`.
- TP7: packet and print/export UI are unreachable because TP6 cannot create `proposal_state`.
