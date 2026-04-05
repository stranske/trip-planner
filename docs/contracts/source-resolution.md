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

## Operational Ingestion Path

Later ingestion pipelines should treat the resolution layer as an explicit checkpoint between raw ingestion and normalized option creation.

1. Start with the raw records already collected in a `RawSnapshot` for one planning slice, such as all lodging records for a destination/date window.
2. Build comparison batches from `RawSourceRecord` values that plausibly refer to the same entity. Each candidate should preserve the compared record ids, snapshot ids, and the signals used to score the comparison.
3. Emit one `MatchCandidate` per comparison outcome. This is the point where provider id matches, geo distance, title similarity, policy alignment, or other inspectable signals become durable data instead of temporary adapter-local heuristics.
4. Consolidate the candidate set into one `EntityResolution` for the canonical entity id the pipeline wants to reason about next.
5. Preserve any unresolved disagreements in `AttributeConflict` entries on the resolution instead of flattening them into a best-effort merged object.
6. Carry forward a `MergedEntityProvenance` bundle so the next stage can explain which raw records and provenance references informed the resolution, even when the records ultimately remain separate.
7. Convert the resolution output into a `DeduplicationDecision` that tells the normalized-object builder whether to merge, keep separate, request review, or suppress a record.
8. Only after the dedup decision is explicit should downstream code materialize normalized planning objects such as `LodgingOption`, `TransportOption`, `DestinationOption`, or `ActivityOption`.

## Worked Example

The sequence below shows the intended handoff from raw ingestion into the resolution contracts.

1. A lodging ingestion job receives two `RawSourceRecord` entries for the same canal-house listing from different providers.
2. The comparison step scores identical provider ids, near-identical coordinates, and matching cancellation-policy text.
3. The pipeline emits a `MatchCandidate` with those record ids plus a score breakdown that explains why the pair is a likely match.
4. Resolution consolidates the candidate into an `EntityResolution(status="match")` with no unresolved conflicts and a `MergedEntityProvenance` bundle referencing both raw records.
5. Deduplication turns that outcome into `DeduplicationDecision(action="merge")`.
6. The normalized lodging builder creates one canonical lodging option and attaches the merged provenance so later ranking, audit, and explainability layers can trace it back to both sources.

## Distinct Outcomes Still Carry Provenance

`EntityResolution(status="distinct")` still requires `MergedEntityProvenance` because the pipeline has already done real comparison work and needs to preserve what was reviewed.

Example:

1. Two walking-tour records share the same neighborhood and title keywords, so they enter the same comparison batch.
2. The records diverge on duration, stop list, and operator identity, so resolution concludes they are genuinely different experiences.
3. The pipeline emits `EntityResolution(status="distinct")` with a canonical resolution id, notes describing the separating evidence, and `MergedEntityProvenance` that names both raw records.
4. Deduplication then chooses `DeduplicationDecision(action="keep_separate")`.
5. Downstream builders create two activity options, but the preserved provenance still documents why the records were compared together and why they were intentionally not merged.

If a caller cannot justify carrying that shared comparison lineage, the caller should not emit a `distinct` resolution object in the first place. It should skip the comparison batch and leave the records as unrelated raw inputs.

## First-Pass Scope

- Covers confident matches, ambiguous matches, and explicit non-matches.
- Preserves conflicting attributes when providers disagree on names, locations, durations, or policy details.
- Leaves ranking and final scoring for later issues; this layer only decides whether records can be safely merged.
