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
    assert "Linked follow-up PRs still missing matching description/body evidence: #581." in prompt


def test_prepare_prompt_requires_matching_description_evidence_for_every_linked_followup_pr(
    monkeypatch,
):
    context = """
### Related Issues/PRs
- [#566](https://github.com/stranske/trip-planner/pull/566)
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Follow-up PR: https://github.com/stranske/trip-planner/pull/582
- PR description: Follow-up PR #581 references #566 in its body.

Pull request: [#583](https://github.com/stranske/trip-planner/pull/583)
""".strip()
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "1")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "Local follow-up reference evidence" in prompt
    assert "Verified from local context" not in prompt
    assert "Linked follow-up PRs still missing matching description/body evidence: #582." in prompt


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


def test_extract_followup_pr_links_supports_wrapped_and_lowercase_entries():
    context = """
## Thread 1
- follow-up pr:
  https://github.com/stranske/trip-planner/pull/581
- Follow-up PR:
  https://github.com/stranske/trip-planner/pull/582

Pull request: [#583](https://github.com/stranske/trip-planner/pull/583)
""".strip()

    assert pr_verifier._extract_followup_pr_links(context) == [
        "https://github.com/stranske/trip-planner/pull/581",
        "https://github.com/stranske/trip-planner/pull/582",
    ]


def test_extract_followup_pr_links_supports_completion_queue_wording():
    context = """
1\tC2\t579\thttps://github.com/stranske/trip-planner/issues/579\t566\thttps://github.com/stranske/trip-planner/pull/566\tUnresolved review threads (2)\tFollow-up PR opened: https://github.com/stranske/trip-planner/pull/581; post disposition + resolve threads when API write access recovers\tpending_remote_write
""".strip()

    assert pr_verifier._extract_followup_pr_links(context) == [
        "https://github.com/stranske/trip-planner/pull/581",
    ]


def test_missing_linked_followup_description_numbers_tracks_each_linked_pr():
    context = """
## Thread 1
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- Follow-up PR: https://github.com/stranske/trip-planner/pull/582
- PR description: Follow-up PR #581 references #566 in its body.
- PR body evidence: Follow-up PR #583 references #566 and #571.

Pull request: [#584](https://github.com/stranske/trip-planner/pull/584)
""".strip()

    assert pr_verifier._missing_linked_followup_description_numbers(context) == [582]


def test_missing_linked_followup_description_numbers_accepts_pr_numbers_without_hash():
    context = """
## Thread 1
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- PR description: Follow-up PR 581 references #566 in its body.

Pull request: [#582](https://github.com/stranske/trip-planner/pull/582)
""".strip()

    assert pr_verifier._missing_linked_followup_description_numbers(context) == []


def test_missing_linked_followup_description_numbers_accepts_originating_pr_without_hash():
    context = """
## Thread 1
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- PR description: Follow-up PR 581 references PR 566 in its body.

Pull request: [#582](https://github.com/stranske/trip-planner/pull/582)
""".strip()

    assert pr_verifier._missing_linked_followup_description_numbers(context) == []


def test_missing_linked_followup_link_numbers_requires_hash_or_pr_url():
    context = """
## Thread 1
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- PR description: Follow-up PR 581 references PR 566 in its body.

Pull request: [#582](https://github.com/stranske/trip-planner/pull/582)
""".strip()

    assert pr_verifier._missing_linked_followup_link_numbers(context, [566]) == [581]


def test_missing_linked_followup_link_numbers_accepts_hash_references():
    context = """
## Thread 1
- Follow-up PR: https://github.com/stranske/trip-planner/pull/581
- PR description: Follow-up PR #581 references #566 in its body.

Pull request: [#582](https://github.com/stranske/trip-planner/pull/582)
""".strip()

    assert pr_verifier._missing_linked_followup_link_numbers(context, [566]) == []


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

    assert "Partially verified from local context" in prompt
    assert "Follow-up PR links recorded in local context" in prompt
    assert "#566" in prompt
    assert "#571" in prompt
    assert (
        "Follow-up PR descriptions must explicitly reference the originating PR(s): #566, #571."
        not in prompt
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


def test_prepare_prompt_accepts_wrapped_body_evidence_for_linked_followup_pr(monkeypatch):
    context = """
## Thread 1
- Follow-up PR:
  https://github.com/stranske/trip-planner/pull/581
- PR body evidence:
  Follow-up PR 581 references #566 in its body.

Pull request: [#582](https://github.com/stranske/trip-planner/pull/582)
""".strip()
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "1")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "Verified from local context" in prompt
    assert "Explicit follow-up PR description evidence" in prompt
    assert "Follow-up PR 581 references #566 in its body." in prompt
    assert "Linked follow-up PRs still missing matching description/body evidence" not in prompt


def test_prepare_prompt_accepts_plain_pr_number_body_evidence(monkeypatch):
    context = """
## Thread 1
- Follow-up PR:
  https://github.com/stranske/trip-planner/pull/581
- PR body evidence:
  Follow-up PR 581 references PR 566 in its body.

Pull request: [#582](https://github.com/stranske/trip-planner/pull/582)
""".strip()
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "1")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "Partially verified from local context" in prompt
    assert "Explicit follow-up PR description evidence" in prompt
    assert "Follow-up PR 581 references PR 566 in its body." in prompt
    assert "GitHub-linkable follow-up PR description evidence" not in prompt
    assert (
        "Linked follow-up PRs still missing GitHub-linkable description/body evidence: #581."
        in prompt
    )
    assert "GitHub-linkable #/URL references are still not fully cached locally" in prompt


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


def test_pr_566_disposition_doc_verifies_only_originating_pr_reference():
    disposition = (REPO_ROOT / "docs" / "pr-566-thread-disposition.md").read_text(encoding="utf-8")

    assert pr_verifier._extract_related_pr_numbers(disposition) == [566, 571]

    summary = pr_verifier._followup_reference_summary(disposition)

    assert "Partially verified from local context" in summary
    assert "text references the originating PR(s): #566, #571." in summary
    assert (
        "Linked follow-up PRs still missing GitHub-linkable description/body evidence: #581."
        in summary
    )


def test_pr_566_disposition_doc_matches_linked_followup_description_evidence():
    disposition = (REPO_ROOT / "docs" / "pr-566-thread-disposition.md").read_text(encoding="utf-8")

    assert pr_verifier._extract_followup_pr_links(disposition) == [
        "https://github.com/stranske/trip-planner/pull/581"
    ]
    assert pr_verifier._missing_linked_followup_description_numbers(disposition) == []
    assert pr_verifier._missing_linked_followup_link_numbers(disposition, [566, 571]) == [581]

    description_evidence = pr_verifier._extract_followup_pr_description_evidence(disposition)
    description_link_evidence = pr_verifier._extract_followup_pr_description_link_evidence(
        disposition,
        [566, 571],
    )

    assert any("PR body evidence:" in line for line in description_evidence)
    assert any("explicitly references PR #566" in line for line in description_evidence)
    assert description_link_evidence == []
