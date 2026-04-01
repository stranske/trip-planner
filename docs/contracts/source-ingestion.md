# Source Ingestion Pipelines

Issue `#528` adds the first category-specific ingestion scaffolding on top of raw snapshots and resolution records.

## Current Scope

- `trip_planner/ingestion/lodging_pipeline.py` turns lodging snapshots into canonical `LodgingOption` objects.
- `trip_planner/ingestion/transport_pipeline.py` turns transport snapshots into canonical `TransportOption` objects.
- Both pipelines emit:
  - normalized options
  - `NormalizationHandoff` metadata for downstream candidate generation
  - explicit ingestion warnings
  - unresolved conflicts that still need review
  - summary metadata that highlights filtered records and low-confidence outputs

## Stage Order

1. Consume a `RawSnapshot` from the adapter layer.
2. Attach any `EntityResolution` or `DeduplicationDecision` records that describe canonical merges.
3. Build normalized option payloads that reuse the existing option contracts instead of inventing a new inventory object.
4. Seed `source_refs` from raw record identity, freshness, and trust signals.
5. Preserve unresolved conflicts and degraded normalization warnings in the result object.
6. Emit a `NormalizationHandoff` plus summary counts so later candidate filtering can skip low-confidence or conflict-heavy outputs.

## Design Rules

- Ingestion can reshape payloads, but it should not perform ranking.
- Resolution and deduplication remain inspectable. Unresolved conflicts stay visible in result metadata and option constraints.
- Pipeline outputs must stay compatible with the option contracts from `#521` and `#522`.
- Candidate generation should consume the result summary rather than re-parsing raw snapshots to find degraded records.

## First-Pass Fixture Strategy

The representative fixtures in `tests/fixtures/ingestion/` intentionally stay small:

- one clean lodging snapshot
- one duplicate/conflicted lodging snapshot
- one clean transport snapshot
- one duplicate/conflicted transport snapshot

This keeps the ingestion layer testable without pretending the repo already has provider-rich adapters.
