# Preference Fixture Corpus

The leisure preference fixture corpus lives at:

- `tests/fixtures/preferences/leisure_traveler_corpus.json`
- `tests/preferences/fixture_corpus.py`

This corpus is intended to be the reusable regression backbone for preference work. It should be used by:

- schema and contract tests
- evidence-model tests
- resolver and contradiction-handling tests
- itinerary-objective derivation tests

## Format

Each fixture contains:

- `id`
  - stable identifier used by tests
- `fixture_kind`
  - `archetype` or `tension_case`
- `summary`
  - terse engineering description of the traveler pattern
- `tags`
  - short clustering labels for discovery and coverage review
- `raw_inputs`
  - compact traveler statements and planning-style notes
- `profile_overrides`
  - canonical leisure-profile overrides layered onto a shared default profile
- `evidence`
  - `PreferenceEvidence` payloads that can be instantiated directly
- `intended_interpretation`
  - qualitative expectations that later tests can assert without freezing final numeric outputs

## Design Rules

- Keep fixtures implementation-focused rather than user-facing.
- Prefer a smaller number of serious fixtures over many shallow personas.
- Model real tensions explicitly instead of averaging them away.
- Use `profile_overrides` only for meaningful deviations from the default baseline.
- When adding option-choice evidence, include realistic comparison context through `option_evidence`.

## Extension Guidance

Add a new fixture when at least one of these is true:

- a first-tier dimension is underrepresented
- a hybrid factor changes route or budget logic in a new way
- a new contradiction pattern needs explicit regression coverage
- a resolver change would otherwise be tested only against one narrow travel style

When extending the corpus:

- keep `id` values stable once published
- update the intended interpretation before adding numeric assertions elsewhere
- add evidence that explains why the profile should resolve the way it does
- prefer new fixtures over mutating old ones when the traveler pattern is materially different

## What Not To Do

- Do not turn the corpus into marketing personas.
- Do not add live booking or destination inventory here.
- Do not use old `request.json` fields as the primary fixture format.
- Do not treat the corpus as a final ranking benchmark; it is for preference-engine regression first.
