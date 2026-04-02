# PR #569 Unresolved Review Threads

Source issue: [#517](https://github.com/stranske/trip-planner/issues/517)  
Follow-up issue: [#588](https://github.com/stranske/trip-planner/issues/588)  
Source PR: [#569](https://github.com/stranske/trip-planner/pull/569)

All five PR #569 review threads were re-reviewed on 2026-04-02. Each thread was classified against the issue criteria, answered directly on the original PR, and resolved on GitHub.

## Thread 1: `Final` annotations for `sources/schema.py`
- **Link:** https://github.com/stranske/trip-planner/pull/569#discussion_r2937872728
- **Technical Concern:** `trip_planner/sources/schema.py` does not use `typing.Final` annotations the way the leisure and business schema modules do.
- **Classification:** not-warranted disposition
- **Justification:** This is a style and static-typing consistency suggestion, not a demonstrated correctness bug or contract break.
- **Resolution:** https://github.com/stranske/trip-planner/pull/569#discussion_r3025824443

## Thread 2: unify `quality_summary` and `quality_value_fit` names in provenance
- **Link:** https://github.com/stranske/trip-planner/pull/569#discussion_r2937872746
- **Technical Concern:** `SourceRecord.quality_summary` and `ProvenanceReference.quality_value_fit` expose the same summary type under different names.
- **Classification:** not-warranted disposition
- **Justification:** The fields live at different contract layers, so renaming them would be a broader API redesign without a demonstrated functional defect.
- **Resolution:** https://github.com/stranske/trip-planner/pull/569#discussion_r3025824754

## Thread 3: optional provenance locator/timestamp validation semantics
- **Link:** https://github.com/stranske/trip-planner/pull/569#discussion_r2937872752
- **Technical Concern:** `locator` and `captured_at` currently use `""` defaults plus `require_optional_non_empty(self.field or None, ...)`, so explicit empty strings are treated the same as omitted values.
- **Classification:** not-warranted disposition
- **Justification:** The source/provenance contracts and loaders already use the empty-string sentinel for optional metadata, so switching to `None` semantics would be a compatibility refactor rather than a PR #569 bug fix.
- **Resolution:** https://github.com/stranske/trip-planner/pull/569#discussion_r3025824992

## Thread 4: optional source metadata validation semantics
- **Link:** https://github.com/stranske/trip-planner/pull/569#discussion_r2937872757
- **Technical Concern:** `base_url` and `default_locale` use the same empty-string-plus-validator pattern as the provenance fields.
- **Classification:** not-warranted disposition
- **Justification:** These fields follow the same established optional-string contract shape used by the source-loading layer, so tightening them to `None`-only semantics would be an API change without a demonstrated behavior failure.
- **Resolution:** https://github.com/stranske/trip-planner/pull/569#discussion_r3025825593

## Thread 5: unify `quality_summary` and `quality_value_fit` names in source models
- **Link:** https://github.com/stranske/trip-planner/pull/569#discussion_r2937872767
- **Technical Concern:** `SourceRecord` and `ProvenanceReference` expose related quality/value/fit summaries under different field names.
- **Classification:** not-warranted disposition
- **Justification:** The naming difference reflects source-level versus provenance-level payloads; standardizing it would impose migration cost without evidence of incorrect behavior.
- **Resolution:** https://github.com/stranske/trip-planner/pull/569#discussion_r3025825828

## Summary
- Total threads: 5
- Warranted fixes: 0
- Dispositioned: 5
- Remaining unresolved on PR #569: 0
