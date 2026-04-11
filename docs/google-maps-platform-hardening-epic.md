# Google Maps And Platform Hardening Epic Plan

This document records the implementation contract for epic `#756`.

The goal is to sequence the next map-provider and hardening work so Google Maps integration, repo bootstrap reliability, and runtime/doc warning cleanup land as separate inspectable concerns instead of one opaque "finish the platform" patch.

## Epic Boundary

Epic `#756` exists to define the delivery order and contract rules for the first provider-backed map surface and the bounded repo/runtime hardening needed to keep the current full-stack app reliable for ongoing product work.

It is complete when:

- the child issues are shipped in dependency order
- the workspace can render a real provider-backed map experience without erasing the bounded fallback seam
- repo bootstrap and dependency layout are stable enough that local setup and CI no longer depend on accidental root-level Node artifacts
- runtime docs and router/test behavior reflect the current full-stack product reality instead of the earlier contracts-only stage

## Current Runtime Posture

The repo now has a usable runtime-backed workspace, but the map and hardening layer is still split between a placeholder visualization path and recently surfaced reliability debt:

- `frontend/src/components/maps/TripMap.tsx` renders a route-context preview from runtime scenario data, but it is still a provider-free textual map surface rather than a real map implementation
- `docs/frontend-route-visualization.md` already establishes the rule that provider output should degrade to textual route summaries instead of moving route logic into the browser
- issue `#766` has already landed on `main` and established the repo-hygiene baseline for frontend bootstrap reliability by removing tracked root `node_modules` and documenting the intended dependency layout
- router warning drift, runtime-check messaging, and design/reality docs still need explicit cleanup so future work is not guided by stale assumptions

That means the app can show route context and pass a cleaner local bootstrap, but it still lacks the provider-backed map path and the remaining warning/doc hardening that should accompany it.

## Dependency Chain

This epic depends on the current persisted-trip runtime and planner workspace surfaces already available on `main`, especially the scenario comparison, workspace map-preview, and frontend route-loading seams introduced by the recent runtime epics.

Within the epic itself, the expected order is:

1. `#766` repo bootstrap hygiene and frontend dependency normalization
2. `#765` Google Maps-backed route and option surface with bounded fallback seam
3. `#767` router warning cleanup, runtime-check messaging, and design/runtime doc refresh

Issue `#766` is already complete on `main` and should be treated as the foundation for the remaining work, not reopened casually. Issue `#765` should build on the provider-independent map data already exposed by the runtime instead of re-deriving route logic in the browser. Issue `#767` should land after or alongside the provider work so documentation and warning cleanup describe the actual post-`#765` runtime rather than another intermediate state.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep provider-specific logic behind a clear frontend adapter seam; do not let `TripMap` own direct Google Maps details and fallback behavior at the same abstraction level.
- Preserve the existing rule that route shaping and feasibility stay upstream in runtime services or a provider-independent client layer rather than being recalculated inside map components.
- Treat provider-backed maps, repo bootstrap reliability, and warning/doc cleanup as separate inspectable concerns even when they share files.
- Keep fallback behavior real and bounded: local development and temporary provider failure should fall back to textual or simplified map presentation instead of breaking the workspace.
- Keep runtime docs factual; do not claim live traffic, turn-by-turn navigation, or other map capabilities that the implementation does not actually ship.
- Use the normalized frontend dependency layout established by `#766`; do not reintroduce repo-root `node_modules` or other bootstrap shortcuts.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#766` | Repo bootstrap hygiene foundation | current frontend install flow, `.gitignore`, runtime/dev scripts, CI assumptions | normalized dependency layout, root `node_modules` guardrails, reliable frontend bootstrap expectations |
| `#765` | Provider-backed map surface | runtime scenario comparison data, `TripMap` contract, route-loading seams, repo hygiene from `#766` | Google Maps adapter boundary, provider-backed workspace map, bounded fallback path, provider-independent map state shaping |
| `#767` | Warning and runtime/doc hardening | router/runtime test surfaces, runtime-check flow, updated map/runtime reality from `#765`, bootstrap expectations from `#766` | reduced router warning drift, clearer runtime-check messaging, refreshed README/design docs, assertions that keep runtime assumptions from drifting |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before richer provider or runtime work expands:

- `frontend/src/components/maps/TripMap.tsx` and adjacent map adapter files for provider-backed rendering with fallback behavior
- frontend config/env seams needed to select and configure the Google Maps path without hard-coding a brittle single-provider assumption
- `frontend/src/router.tsx`, router tests, and runtime-check docs/scripts for warning cleanup and truthful prerequisite messaging
- README and design references that describe the current runtime, map posture, and explicitly deferred gaps

This keeps later mapping, routing intelligence, and provider expansion additive instead of forcing those lanes to simultaneously establish the first real provider seam and clean up unrelated repo drift.

## Acceptance Mapping

The epic acceptance criteria from `#756` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the map-provider and hardening lane are complete | `#765`, `#766`, `#767` |
| The app has a real provider-backed map path with a bounded fallback seam | `#765`, supported by `#766` and documented by `#767` |
| Known repo/runtime hardening risks are explicitly resolved rather than left as vague debt | `#766`, `#767` |

## Relationship To Existing Docs

The repo already contains broader visualization and runtime references such as [maps-timeline-comparison-epic.md](maps-timeline-comparison-epic.md), [frontend-route-visualization.md](frontend-route-visualization.md), [frontend-route-loading-foundation.md](frontend-route-loading-foundation.md), and [langchain-planner-runtime-epic.md](langchain-planner-runtime-epic.md). Those remain useful design references, but epic `#756` is the active sequencing contract for turning the current route-context preview into a provider-backed map surface while finishing the immediate repo/runtime hardening that surfaced during recent implementation review.

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Implementation plan](implementation-plan.md)
- [Maps, timeline, and comparison application surfaces epic plan](maps-timeline-comparison-epic.md)
- [Live runtime completion epic plan](live-runtime-completion-epic.md)
- [LangChain planner runtime epic plan](langchain-planner-runtime-epic.md)
- [Frontend route visualization](frontend-route-visualization.md)
- [Frontend route loading foundation](frontend-route-loading-foundation.md)
- [Frontend trip workspace](frontend-trip-workspace.md)
- [Planner UI integration](planner-ui-integration.md)

## Working Rule

If a child issue tries to hide Google Maps integration, fallback behavior, repo bootstrap fixes, and warning/doc cleanup inside one oversized patch or one provider-specific component rewrite, the epic is being violated and the design should be corrected before the PR lands.
