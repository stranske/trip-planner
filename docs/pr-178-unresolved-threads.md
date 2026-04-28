# PR #178 Unresolved Thread Inventory

This file tracks the unresolved inline review threads for PR #178 and records whether each item needs a code fix or a disposition-only response.

## Status

As of April 28, 2026, PR #178 still exposes 4 unresolved review threads in the public GitHub conversation HTML (`review-thread-collapsible data-resolved="false"`). This means the "zero unresolved threads" acceptance criterion is still open until those threads are resolved in the GitHub UI.

The inventory below is now populated from the live PR #178 conversation page and includes thread IDs, thread URLs, locations, classifications, and rationales.

The repo supports loading review threads from a local JSON snapshot via `node scripts/list_unresolved_pr_threads.js --input <path>`.
It also supports `--expect-count <n>` so the same command can fail fast when the unresolved-thread count does not match the expected state.

When a verified snapshot or `GITHUB_TOKEN` is available, use one of these commands:

```bash
node scripts/list_unresolved_pr_threads.js stranske/trip-planner 178 --format markdown --expect-count 4
node scripts/list_unresolved_pr_threads.js stranske/trip-planner 178 --input path/to/pr-178-review-threads.json --format markdown --expect-count 4
node scripts/list_unresolved_pr_threads.js stranske/trip-planner 178 --input path/to/pr-178-review-threads.json --write-inventory-doc docs/pr-178-unresolved-threads.md --expect-count 4
```

After the inventory is populated, identify any `fix`-classified entries with:

```bash
node scripts/list_fix_threads_from_doc.js docs/pr-178-unresolved-threads.md
```

To generate a bounded follow-up PR title/body payload for each `fix`-classified PR group, run:

```bash
node scripts/list_fix_threads_from_doc.js docs/pr-178-unresolved-threads.md --format pr-payload --exclude-outdated
```

To generate a shell-ready `gh pr create` command plus the matching markdown body for each bounded follow-up PR group, run:

```bash
node scripts/list_fix_threads_from_doc.js docs/pr-178-unresolved-threads.md --format gh-cli --exclude-outdated
```

To also write the referenced PR body files, executable `gh pr create` helper scripts, plus a `manifest.json` that captures the exact grouped `gh pr create` commands, run:

```bash
node scripts/list_fix_threads_from_doc.js docs/pr-178-unresolved-threads.md --format gh-cli --exclude-outdated --write-artifacts-dir .tmp/pr-thread-payloads
```

That artifact directory now includes one `pr-178-fix-group-*-create.sh` script per follow-up PR group so the generated `gh pr create` invocation can be executed directly after the branch is ready.

To dry-run or execute those grouped PR creations from the generated `manifest.json`, use:

```bash
node scripts/create_follow_up_prs_from_manifest.js --manifest .tmp/pr-thread-payloads/manifest.json
node scripts/create_follow_up_prs_from_manifest.js --manifest .tmp/pr-thread-payloads/manifest.json --follow-up-pr https://github.com/stranske/trip-planner/pull/581 --execute
```

Additional usage notes are captured in `docs/pr-178-follow-up-pr-creation.md`.

To generate a bounded checklist for any `disposition`-classified entries that still need a PR comment, run:

```bash
node scripts/list_disposition_threads_from_doc.js docs/pr-178-unresolved-threads.md --format plan --exclude-outdated
```

To generate ready-to-post disposition comment drafts for those unresolved threads, run:

```bash
node scripts/list_disposition_threads_from_doc.js docs/pr-178-unresolved-threads.md --format comments --exclude-outdated
```

To generate shell-ready `gh api graphql` commands for posting each disposition reply and resolving the matching review thread once GitHub write access is available, run:

```bash
node scripts/list_disposition_threads_from_doc.js docs/pr-178-unresolved-threads.md --format gh-cli --exclude-outdated
```

To also write executable helper scripts plus a `manifest.json` for those disposition replies/resolutions, run:

```bash
node scripts/list_disposition_threads_from_doc.js docs/pr-178-unresolved-threads.md --format gh-cli --exclude-outdated --write-artifacts-dir .tmp/pr-thread-disposition
```

To dry-run or execute those disposition replies/resolutions from the generated `manifest.json`, use:

```bash
node scripts/resolve_disposition_threads_from_manifest.js --manifest .tmp/pr-thread-disposition/manifest.json
node scripts/resolve_disposition_threads_from_manifest.js --manifest .tmp/pr-thread-disposition/manifest.json --thread-id THREAD_ID --execute
```

To verify that the populated inventory matches an exported review-thread snapshot before classifying or resolving items, run:

```bash
node scripts/verify_pr_thread_inventory.js stranske/trip-planner 178 --doc docs/pr-178-unresolved-threads.md --input path/to/pr-178-review-threads.json --expect-doc-count 4 --expect-count 4
```

The verifier now checks that each documented thread ID, original thread URL, location, and content match the unresolved-thread snapshot, so copy the generated markdown carefully before adding classifications and rationales.

After the fix/disposition work is complete, rerun the same command with `--expect-count 0` to verify the acceptance criterion.

To summarize the local repo state against the acceptance criteria before doing any GitHub UI follow-up, run:

```bash
node scripts/check_pr_thread_acceptance.js --doc docs/pr-178-unresolved-threads.md
node scripts/check_pr_thread_acceptance.js --doc docs/pr-178-unresolved-threads.md --input path/to/pr-178-review-threads.json
node scripts/check_pr_thread_acceptance.js --doc docs/pr-178-unresolved-threads.md --input path/to/pr-178-review-threads.json --github-ui-confirmed
node scripts/check_pr_thread_acceptance.js --results .tmp/pr-thread-disposition/results.json
```

The acceptance checker fails loudly when the inventory is still incomplete, and it only performs live GitHub API verification when you opt in with `--live`.
Use `--github-ui-confirmed` only after manually confirming in the PR #178 GitHub UI that no unresolved inline review threads remain.
Use `--results` to reuse a persisted `resolve_disposition_threads_from_manifest.js --write-results ...` artifact instead of manually re-entering the doc path, PR number, and remaining snapshot path.

## Thread Inventory

### Thread 1

- Thread ID: 1762828877
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2684232287
- Location: `.github/workflows/autofix.yml` (line 117 in the reviewed diff)
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/622
- Rationale: Reviewer requested a wording correction from `autofix-loop` to `keepalive-loop`; current workflow text no longer uses `autofix-loop`, so this is treated as fixed via follow-up updates.
- Content: The comment says the note should reference `keepalive-loop` instead of `autofix-loop`.
- Outdated: no

### Thread 2

- Thread ID: 1762828888
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2684232300
- Location: `.github/workflows/agents-keepalive-loop.yml` (line 38 in the reviewed diff)
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/622
- Rationale: Reviewer flagged `FALLBACK_TOKEN` as unused. Current workflow no longer declares that variable, so this is treated as fixed via follow-up updates.
- Content: The comment asks to remove an unused workflow-level `FALLBACK_TOKEN` environment variable.
- Outdated: no

### Thread 3

- Thread ID: 1762828901
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2684232315
- Location: `.github/workflows/agents-63-issue-intake.yml` (line 112 context in the reviewed diff)
- Classification: fix
- Follow-up PR: https://github.com/stranske/trip-planner/pull/622
- Rationale: Same wording correction request as Thread 1; current workflow references `keepalive-loop`, so this is treated as fixed via follow-up updates.
- Content: The comment says the note should reference `keepalive-loop` instead of `autofix-loop`.
- Outdated: no

### Thread 4

- Thread ID: 1762828908
- Original Thread URL: https://github.com/stranske/trip-planner/pull/178#discussion_r2684232323
- Location: `.github/workflows/agents-63-issue-intake.yml` (line 183 in the reviewed diff)
- Classification: disposition
- Follow-up PR: N/A
- Rationale: Reviewer asked for intent validation of `mode: "create"` and `force_mode: true`. Current workflow still carries that behavior intentionally; this requires a PR-thread disposition comment/resolve action in GitHub UI rather than additional code change in this repo.
- Content: The comment asks to verify and document the intentional behavior change from `invite` to `create` with forced mode.
- Outdated: no
