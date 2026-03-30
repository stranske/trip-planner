import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.langchain import pr_verifier


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

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "1")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "Follow-up Iteration Context" in prompt
    assert "Local follow-up reference evidence" in prompt
    assert "#566" in prompt
    assert (
        "Follow-up PR descriptions must explicitly reference the originating PR(s): #566." in prompt
    )


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
- Local verification note: `git show --format=fuller --no-patch 88a850b8` confirms the
  merged PR #581 title was `Follow-up fixes for audit gaps on PRs #566 and #571 (#581)`.

Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)
""".strip()
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "1")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "Local follow-up reference evidence" in prompt
    assert "#566" in prompt
    assert "#571" in prompt
    assert (
        "Follow-up PR descriptions must explicitly reference the originating PR(s): #566, #571."
        in prompt
    )


def test_prepare_prompt_flags_missing_followup_reference_evidence(monkeypatch):
    context = "Pull request: [#581](https://github.com/stranske/trip-planner/pull/581)"
    diff = "diff --git a/docs/pr-566-thread-disposition.md b/docs/pr-566-thread-disposition.md"

    monkeypatch.setenv("CHAIN_DEPTH", "2")
    prompt = pr_verifier._prepare_prompt(context, diff)

    assert "External evidence required" in prompt
    assert "PR-body linkage must be verified in GitHub" in prompt
    assert "description references as satisfied" in prompt
