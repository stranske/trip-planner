# PR #178 Unresolved Thread Inventory

This file tracks the unresolved inline review threads for PR #178 and records whether each item needs a code fix or a disposition-only response.

## Status

The repo now supports loading review threads from a local JSON snapshot via `node scripts/list_unresolved_pr_threads.js --input <path>`.
It also supports `--expect-count <n>` so the same command can fail fast when the unresolved-thread count does not match the expected live PR state.

The exact 4 unresolved threads for PR #178 are still not available in this environment because live GitHub review-thread access is blocked and no exported PR #178 snapshot is checked into the repository yet.

The checked-in fixture at `tests/fixtures/scripts/review_threads_snapshot.json` is synthetic test data only. It must not be used to classify or disposition PR #178 review threads.

When a verified snapshot or `GITHUB_TOKEN` is available, use one of these commands before populating the sections below:

```bash
node scripts/list_unresolved_pr_threads.js stranske/trip-planner 178 --format markdown --expect-count 4
node scripts/list_unresolved_pr_threads.js stranske/trip-planner 178 --input path/to/pr-178-review-threads.json --format markdown --expect-count 4
node scripts/list_unresolved_pr_threads.js stranske/trip-planner 178 --input path/to/pr-178-review-threads.json --write-inventory-doc docs/pr-178-unresolved-threads.md --expect-count 4
```

After the inventory is populated, identify any `fix`-classified entries with:

```bash
node scripts/list_fix_threads_from_doc.js docs/pr-178-unresolved-threads.md
```

To generate a bounded checklist for any `disposition`-classified entries that still need a PR comment, run:

```bash
node scripts/list_disposition_threads_from_doc.js docs/pr-178-unresolved-threads.md --format plan --exclude-outdated
```

To verify that the populated inventory matches an exported review-thread snapshot before classifying or resolving items, run:

```bash
node scripts/verify_pr_thread_inventory.js stranske/trip-planner 178 --doc docs/pr-178-unresolved-threads.md --input path/to/pr-178-review-threads.json --expect-doc-count 4 --expect-count 4
```

The verifier now checks that each documented thread ID, original thread URL, location, and content match the unresolved-thread snapshot, so copy the generated markdown carefully before adding classifications and rationales.

After the fix/disposition work is complete, rerun the same command with `--expect-count 0` to verify the acceptance criterion.

## Thread Template

### Thread 1

- Thread ID:
- Original Thread URL:
- Location:
- Classification:
- Follow-up PR:
- Rationale:
- Content:
- Outdated:

### Thread 2

- Thread ID:
- Original Thread URL:
- Location:
- Classification:
- Follow-up PR:
- Rationale:
- Content:
- Outdated:

### Thread 3

- Thread ID:
- Original Thread URL:
- Location:
- Classification:
- Follow-up PR:
- Rationale:
- Content:
- Outdated:

### Thread 4

- Thread ID:
- Original Thread URL:
- Location:
- Classification:
- Follow-up PR:
- Rationale:
- Content:
- Outdated:
