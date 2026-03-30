import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.langchain import pr_verifier

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_extract_related_pr_numbers_ignores_current_pr_and_issues():
    context = """
### Related Issues/PRs
- [#515](https://github.com/stranske/trip-planner/issues/515)
- [#566](https://github.com/stranske/trip-planner/pull/566)
- Follow-up PR #581 keeps the audit trail intact

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()

    assert pr_verifier._extract_related_pr_numbers(context) == [566]


def test_prepare_prompt_includes_followup_reference_summary(monkeypatch):
    context = """
### Related Issues/PRs
- [#566](https://github.com/stranske/trip-planner/pull/566)
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "1")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "Follow-up Iteration Context" in prompt
    assert "Local follow-up reference evidence" in prompt
    assert "#566" in prompt
    assert "Follow-up PR links recorded in local context" in prompt
    assert "https://github.com/stranske/trip-planner/pull/581" in prompt
    assert (
        "Follow-up PR descriptions must explicitly reference the originating PR(s): #566." in prompt
    )


def test_followup_reference_summary_detects_local_pr_body_evidence(monkeypatch):
    context = """
### Related Issues/PRs
- [#566](https://github.com/stranske/trip-planner/pull/566)
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- PR description: Follow-up PR #581 references #566 in its body.

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "1")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "Verified from local context" in prompt
    assert "Follow-up PR links recorded in local context" in prompt
    assert "Explicit follow-up PR description evidence" in prompt
    assert "PR description: Follow-up PR #581 references #566 in its body." in prompt
    assert "description/body explicitly references the originating PR(s): #566." in prompt
    assert "External evidence required" not in prompt


def test_prepare_prompt_requires_description_evidence_for_the_linked_followup_pr(monkeypatch):
    context = """
### Related Issues/PRs
- [#566](https://github.com/stranske/trip-planner/pull/566)
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- PR description: Follow-up PR #582 references #566 in its body.

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "1")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "Local follow-up reference evidence" in prompt
    assert "PR description: Follow-up PR #582 references #566 in its body." in prompt
    assert "Verified from local context" not in prompt
    assert "description/body explicitly references the originating PR(s): #566." not in prompt


def test_extract_followup_pr_description_evidence_deduplicates_matching_lines():
    context = """
## Thread 1
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- PR description: Follow-up PR #581 references #566 in its body.
- PR description: Follow-up PR #581 references #566 in its body.
- PR body evidence: Follow-up PR #582 references #566 and #571.

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()

    assert pr_verifier._extract_followup_pr_description_evidence(context) == [
        "- PR description: Follow-up PR #581 references #566 in its body.",
        "- PR body evidence: Follow-up PR #582 references #566 and #571.",
    ]


def test_extract_followup_pr_merge_metadata_evidence_deduplicates_matching_lines():
    context = """
## Thread 1
- Local verification note: `git show --format=fuller --no-patch 88a850b8` confirms the merged PR #581 title was `Follow-up fixes for audit gaps on PRs #566 and #571 (#581)`.
- Local verification note: `git show --format=fuller --no-patch 88a850b8` confirms the merged PR #581 title was `Follow-up fixes for audit gaps on PRs #566 and #571 (#581)`.
- Local verification note: `git show --format=fuller --no-patch 88a850b8` confirms the merged PR #581 body included `Address audit follow-up gaps for PRs 566 and 571`.

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()

    assert pr_verifier._extract_followup_pr_merge_metadata_evidence(context) == [
        "- Local verification note: `git show --format=fuller --no-patch 88a850b8` confirms the merged PR #581 title was `Follow-up fixes for audit gaps on PRs #566 and #571 (#581)`.",
        "- Local verification note: `git show --format=fuller --no-patch 88a850b8` confirms the merged PR #581 body included `Address audit follow-up gaps for PRs 566 and 571`.",
    ]


def test_extract_followup_pr_links_deduplicates_links():
    context = """
## Thread 1
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Follow-up PR: https://github.com/stranske/trip-planner/pull/582

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()

    assert pr_verifier._extract_followup_pr_links(context) == [
        "https://github.com/stranske/trip-planner/pull/581",
        "https://github.com/stranske/trip-planner/pull/582",
    ]


def test_extract_related_pr_numbers_supports_plural_pr_commit_titles():
    context = """
### Verification Notes
- `git show --format=fuller --no-patch 88a850b8` confirms the merged PR #581 title was
  `Follow-up fixes for audit gaps on PRs #566 and #571 (#581)`.

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()

    assert pr_verifier._extract_related_pr_numbers(context) == [566, 571]


def test_prepare_prompt_uses_commit_title_evidence_for_followup_reference(monkeypatch):
    context = """
## Thread 1
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Local verification note: `git show --format=fuller --no-patch 88a850b8` confirms the
  merged PR #581 title was `Follow-up fixes for audit gaps on PRs #566 and #571 (#581)`.

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "1")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "Local follow-up reference evidence" in prompt
    assert "Follow-up PR links recorded in local context" in prompt
    assert "#566" in prompt
    assert "#571" in prompt
    assert (
        "Follow-up PR descriptions must explicitly reference the originating PR(s): #566, #571."
        in prompt
    )


def test_prepare_prompt_reports_partial_verification_for_merge_metadata(monkeypatch):
    context = """
## Thread 1
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Local verification note: `git show --format=fuller --no-patch 88a850b8` confirms the merged PR #581 title was `Follow-up fixes for audit gaps on PRs #566 and #571 (#581)`.
- Local verification note: `git show --format=fuller --no-patch 88a850b8` confirms the merged PR #581 body included `Address audit follow-up gaps for PRs 566 and 571`.

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "1")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "Partially verified from local context" in prompt
    assert "Explicit follow-up PR merge metadata evidence" in prompt
    assert (
        "GitHub-generated merge metadata for the follow-up PR references the originating PR(s)"
        in prompt
    )
    assert "The PR description/body text is still not cached locally" in prompt
    assert "#566" in prompt
    assert "#571" in prompt
    assert "Verified from local context" not in prompt


def test_prepare_prompt_flags_missing_followup_reference_evidence(monkeypatch):
    context = "Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)"
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "2")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "External evidence required" in prompt
    assert "No follow-up PR links were recorded in the local context." in prompt
    assert "PR-body linkage must be verified in GitHub" in prompt
    assert "description references as satisfied" in prompt


def test_pr_566_disposition_doc_records_followup_pr_link_and_description_evidence():
    disposition = (REPO_ROOT / "docs" / "pr-566-thread-disposition.md").read_text(encoding="utf-8")

    assert "Follow-up PR: https://github.com/stranske/trip-planner/pull/581" in disposition
    assert "merged PR #581 body included" in disposition
    assert "explicitly references PR #566" in disposition
