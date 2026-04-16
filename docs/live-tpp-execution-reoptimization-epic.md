# Live Travel-Plan-Permission Execution And Reoptimization Epic Plan

This document records the implementation contract for epic `#755`.

The goal is to sequence the app-side `Travel-Plan-Permission` integration so real HTTP transport and result-driven planner follow-up land as separate inspectable seams instead of one opaque "make policy live" patch.

## Epic Boundary

Epic `#755` exists to define the delivery order and contract rules for turning the current local or passive `Travel-Plan-Permission` integration into a real cross-repo execution path.

It is complete when:

- the child issues are shipped in dependency order
- `trip-planner` uses a real transport-backed client for policy and proposal flows instead of passive local envelopes
- live `Travel-Plan-Permission` responses drive explicit planner follow-up and reoptimization state in the app runtime
- cross-repo dependencies stay explicit so this repo remains responsible for planning and reaction while `Travel-Plan-Permission` remains authoritative for policy evaluation

## Current Runtime Posture

The repo already has strong business-planning contracts and planner-side workflow scaffolding, but the live policy execution loop is still incomplete:

- `trip_planner/app/services/policy.py` and `trip_planner/app/services/proposal.py` expose app-facing seams for policy and proposal behavior
- `trip_planner/integrations/tpp/` defines transport, submission, results, and reoptimization scaffolds, but the runtime still relies on passive or local envelope handling instead of a real remote execution path
- `docs/contracts/tpp-execution-contracts.md`, `docs/contracts/trip-plan-proposal.md`, and `docs/contracts/tpp-reoptimization.md` already define the intended cross-repo exchange vocabulary
- the earlier [Budget and business policy execution epic plan](budget-business-policy-execution-epic.md) established a local workspace-facing business workflow, but it did not finish the newer app-side live transport and result-driven follow-up behavior now tracked under `#755`

That means the app can model policy-facing planning state, but it still does not complete a real policy round-trip through `Travel-Plan-Permission` and then drive deterministic runtime follow-up from the returned result.

For local contributor setup, that also means the shipped MVP must stay honest about configuration:

- `TPP_BASE_URL`, `TPP_ACCESS_TOKEN`, and `TPP_OIDC_PROVIDER` are optional integration env vars, not baseline runtime prerequisites
- when those env vars are absent, the repo should continue to surface passive or stored-policy seams rather than implying live remote policy execution
- runtime-check messaging should distinguish missing local dependencies from intentionally unconfigured remote TPP transport

## Dependency Chain

This epic depends on the persisted-trip runtime seams from `#753`, the planner runtime sequencing from `#754`, and the existing TPP contract docs already established in this repo, because live policy execution needs stable trip/workspace identity, planner-facing runtime state, and explicit cross-repo contracts before it can replace passive local behavior coherently.

Within the epic itself, the expected order is:

1. `#763` real HTTP transport for policy and proposal flows
2. `#764` live evaluation, reoptimization, and follow-up state from `Travel-Plan-Permission` results

Issue `#764` should build on the transport-backed execution seam from `#763` instead of introducing its own network or polling path. Any required `Travel-Plan-Permission` support should be called out as an explicit cross-repo dependency rather than hidden inside `trip-planner` fallback logic.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep transport and execution semantics in `trip_planner/integrations/tpp/`; do not leak HTTP or retry behavior into planner-domain contracts.
- Keep `trip-planner` responsible for planning, proposal packaging, and planner-side reaction while `Travel-Plan-Permission` remains authoritative for policy evaluation and approval posture.
- Treat transport-backed execution and result-driven planner follow-up as separate seams even if one workspace payload ultimately displays both.
- Preserve correlation IDs, request IDs, and result lineage across the whole cross-repo round-trip so later issue and verification work can inspect what happened deterministically.
- Make planner follow-up consume structured `PolicyEvaluationResult` outputs rather than re-implementing policy logic locally.
- Keep bounded degraded behavior explicit: if live policy transport is unavailable, the runtime should surface that state clearly instead of implying a successful authoritative evaluation.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#763` | Live TPP transport boundary | existing TPP execution contracts, policy/proposal service seams, current proposal and policy payload contracts | real HTTP-backed client path, explicit request/response handling, correlation and failure semantics that the app runtime can inspect |
| `#764` | Result-driven runtime follow-up | transport seam from `#763`, structured `PolicyEvaluationResult` outputs, current planner/workspace/scenario state | live evaluation ingestion, deterministic reoptimization/follow-up state, workspace-visible business-trip reaction to authoritative TPP results |

## Cross-Repo Dependency Surface

The app-side work in this epic depends on a stable planner-facing API from `Travel-Plan-Permission`. At minimum, the child issues should keep these cross-repo expectations explicit:

- policy and proposal requests must move through a real remote transport instead of local placeholder storage
- correlation and result lookup semantics must stay stable enough for the app to resume, refresh, or inspect a policy round-trip
- returned evaluation payloads must preserve the structured decision, failure, preferred-alternative, and approval-guidance fields already modeled in this repo's contracts

Known cross-repo dependency records for this epic should be maintained here as they are confirmed in the child issues:

- `#763` -> matching `Travel-Plan-Permission` issue/PR for real HTTP policy/proposal submission and result lookup support
- `#764` -> matching `Travel-Plan-Permission` issue/PR for structured evaluation-result fields and any follow-up or reoptimization inputs consumed by `trip-planner`

If `trip-planner` needs additional remote fields or endpoints, document the dependency under the relevant child issue above and link the matching `Travel-Plan-Permission` work instead of papering over the gap with local heuristics.

## Contract Surface

The first pass of this epic should stabilize the following surfaces before broader business workflow or planner UX work expands:

- `trip_planner/integrations/tpp/` for live transport, execution status, and result-ingestion seams
- `trip_planner/app/services/policy.py` and `trip_planner/app/services/proposal.py` for app-facing orchestration over the transport layer
- planner/workspace-visible follow-up state in the existing app runtime so business-trip users can see what changed after a real policy response
- tests and fixtures that prove the app can move from proposal submission through result-driven reoptimization without replacing `Travel-Plan-Permission` as the policy authority

This keeps later business-trip product work additive instead of forcing unrelated planner or UI changes to bootstrap the first real cross-repo execution path.

## Acceptance Mapping

The epic acceptance criteria from `#755` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the live app-side TPP execution path are complete | `#763`, `#764` |
| Cross-repo dependencies on `Travel-Plan-Permission` are explicit and linked | `#763`, `#764` |
| A business trip can complete a real policy transport round-trip and surface the resulting follow-up state in the app runtime | `#763`, `#764` |

## Relationship To Existing Docs

The repo already contains earlier TPP and business workflow references such as [policy-integration-execution-epic.md](policy-integration-execution-epic.md), [budget-business-policy-execution-epic.md](budget-business-policy-execution-epic.md), [contracts/tpp-execution-contracts.md](contracts/tpp-execution-contracts.md), and [contracts/tpp-reoptimization.md](contracts/tpp-reoptimization.md). Those remain important design references, but epic `#755` is the active sequencing contract for finishing the live app-side `Travel-Plan-Permission` round-trip and should be treated as the parent lane for issues `#763` and `#764`.

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Live runtime completion epic plan](live-runtime-completion-epic.md)
- [LangChain planner runtime epic plan](langchain-planner-runtime-epic.md)
- [Budget and business policy execution epic plan](budget-business-policy-execution-epic.md)
- [Policy integration execution and approval-ready workflows epic plan](policy-integration-execution-epic.md)
- [Policy-facing proposal contracts](contracts/trip-plan-proposal.md)
- [TPP execution contracts](contracts/tpp-execution-contracts.md)
- [TPP reoptimization and exception routing](contracts/tpp-reoptimization.md)

## Working Rule

If a child issue tries to hide real transport, authoritative policy results, and planner-side follow-up inside one oversized integration helper or another passive local envelope path, the epic is being violated and the design should be corrected before the PR lands.
