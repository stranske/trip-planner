# PR #566 Thread Disposition

This document records the two unresolved inline review threads still associated with PR #566.

## Thread 1

- Thread identifier: `pr-566-thread-1`
- Context: `tests/business/test_profile.py` loaded JSON fixtures through a cwd-relative path in PR #566. Local git history shows that this was later hardened in commit `f8060844` on branch `codex/issue-579`, and the same gap was also tracked in follow-up PR #581 on `main`.
- Original comment content: "The local checkout does not retain the original GitHub review text. The follow-up code history indicates the thread called out cwd-dependent fixture loading in `tests/business/test_profile.py`."
- Disposition decision: `fix-warranted`
- Rationale: The original helper used `Path(\"tests/fixtures/business\")`, which breaks when tests run from a directory other than the repository root. The subsequent fix switches to a path derived from `__file__`, and the regression test now verifies loading all three fixtures after changing cwd.
- Specific code change needed: Resolve fixture paths relative to `tests/business/test_profile.py` instead of the process cwd, and keep a regression test that changes cwd before loading fixtures.
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Local verification note: `git show --format=fuller --no-patch 88a850b8` confirms the merged PR #581 title was `Follow-up fixes for audit gaps on PRs #566 and #571 (#581)` and its merge message body included `Address audit follow-up gaps for PRs 566 and 571`. Together with the `Follow-up PR:` link above, that gives strong local evidence that PR #581 was framed as a follow-up to PR #566. The GitHub PR description/body field is still not stored in the local checkout, so confirming description-level linkage remains a human GitHub check.
- Comment template: `Disposition: fix-warranted. The fixture loader in tests/business/test_profile.py was cwd-dependent. Follow-up PR #581 carried the path hardening, and this branch keeps the equivalent regression coverage so the helper resolves fixtures relative to the test file instead of the working directory.`

## Thread 2

- Thread identifier: `pr-566-thread-2`
- Context: The repository metadata available in this checkout confirms that PR #566 still has a second unresolved thread, but the original GitHub thread payload is not cached locally and the current execution environment cannot reach the GitHub API.
- Original comment content: "Unavailable from local repository artifacts. A human with GitHub access needs to copy the exact review comment into this entry before posting the final disposition back to PR #566."
- Disposition decision: `pending-human-recovery`
- Rationale: There is enough local evidence to confirm the thread still exists, but not enough to reconstruct its exact original comment without inventing review text. Preserving that uncertainty is safer than fabricating a disposition that cannot be verified against the actual thread.
- Specific code change needed: Pending recovery of the original thread text from GitHub.
- Follow-up PR: None yet. Re-evaluate after the original thread text is recovered.
- Comment template: `I could not verify the exact original review text for this unresolved PR #566 thread from the local checkout because the GitHub API is unavailable in this environment. Please recover the thread content in GitHub before posting a final fix-or-dismiss disposition so the response stays tied to the actual reviewer feedback.`
