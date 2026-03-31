# Source Adapter And Raw Snapshot Contracts

Issue `#526` adds the ingestion boundary that sits between provider-specific fetch code and the planner's normalized contracts.

## Core Contracts

- `SourceAdapter`: provider-facing interface that fetches raw source data and emits a stable handoff for downstream normalization.
- `SourceQuery`: the canonical fetch/read request shape. It keeps market, locale, trip, and destination context explicit instead of burying them inside provider-specific request objects.
- `RawSourceRecord`: one provider entity or document inside a snapshot.
- `RawSnapshot`: the canonical wrapper for fetched payloads, query context, freshness timing, partial failures, and handoff status.
- `AdapterIssue`: explicit observability and degradation record for unavailable providers, stale data, decode failures, and partial payloads.
- `NormalizationHandoff`: the stable downstream boundary. Candidate-generation code consumes this wrapper plus provenance seeds instead of reaching back into transport envelopes directly.

## Design Rules

1. Provider-specific clients own transport details and authentication.
2. Adapters return `RawSnapshot` even when the provider degrades, so downstream code can see partial records and explicit issues at the same time.
3. Downstream normalization starts from `NormalizationHandoff`, not from provider response wrappers.
4. Provenance should be seeded at handoff time using `ProvenanceReference`, so later option contracts can keep source explanations without duplicating raw provider metadata inline.

## Adding A New Adapter

1. Create a `SourceRecord` for the provider category and trust posture.
2. Implement a `SourceAdapter` that converts provider fetch/read operations into `RawSnapshot`.
3. Preserve provider entity identity in each `RawSourceRecord`.
4. Record degraded, stale, or unavailable states in `AdapterIssue` rather than hiding them in logs only.
5. Emit a `NormalizationHandoff` that names the downstream contract and the record ids that are safe to consume next.
6. Add representative raw fixtures and unit tests before adding live network behavior.

## Why This Boundary Exists

The planner should not let lodging, transport, destination, or policy code bind directly to one provider's envelope. The adapter layer keeps:

- provider transport details localized
- provenance and freshness explicit
- partial failures visible
- downstream normalization portable across commercial, editorial, and managed-travel sources
