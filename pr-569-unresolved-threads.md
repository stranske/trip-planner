# PR #569 Unresolved Review Threads

Blocked in this workspace: the repository does not include the five unresolved PR #569 review-thread permalinks or comment bodies, and this run does not have GitHub API access to fetch them.

Once a saved review-thread export is available locally, regenerate this report with:

```bash
python scripts/render_pr_review_thread_report.py \
  --input path/to/pr-569-review-threads.json \
  --output pr-569-unresolved-threads.md \
  --require-count 5
```

The generator accepts either:

- A normalized JSON payload with top-level `pullRequest` and `threads` keys.
- A GitHub GraphQL response containing `data.repository.pullRequest.reviewThreads.nodes`.
