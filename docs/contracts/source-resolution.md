# Source Resolution And Deduplication Contracts

Issue `#527` defines the inspectable matching layer that sits after raw snapshots and before normalized planning objects.

## Core Contracts

- `MatchCandidate`: one candidate alignment between raw source records, including the match strategy, confidence, and per-signal score breakdown.
- `AttributeConflict`: explicit preservation of conflicting source attributes so low-confidence disagreements do not get overwritten silently.
- `MergedEntityProvenance`: the shared provenance wrapper that carries raw record ids, snapshot ids, and `ProvenanceReference` entries into later normalized contracts.
- `EntityResolution`: the overall resolution outcome for a candidate entity, including match status, preserved conflicts, and whether review is still required.
- `DeduplicationDecision`: the downstream dedup action that either merges duplicates, keeps them separate, requests review, or suppresses a record.

## Design Rules

1. Resolution is inspectable. Confidence lives beside score breakdowns and match strategy, not inside opaque provider code.
2. Low-confidence or conflicting attributes stay in `AttributeConflict` instead of disappearing during merge.
3. Dedup decisions always preserve the raw source lineage required to explain the final normalized object.
4. The same contract family should represent destinations, lodging options, transport options, and activity options.

## Pipeline Placement

1. Adapters emit `RawSnapshot`.
2. Resolution code compares `RawSourceRecord` instances and emits `EntityResolution`.
3. Deduplication converts those outcomes into `DeduplicationDecision`.
4. Normalized planning-object builders consume the dedup output plus merged provenance.

## First-Pass Scope

- Covers confident matches, ambiguous matches, and explicit non-matches.
- Preserves conflicting attributes when providers disagree on names, locations, durations, or policy details.
- Leaves ranking and final scoring for later issues; this layer only decides whether records can be safely merged.
