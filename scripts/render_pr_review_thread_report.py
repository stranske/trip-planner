"""Render a markdown report for unresolved PR review threads from a saved GitHub export."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WARRANTED_FIX = "warranted fix"
NOT_WARRANTED_DISPOSITION = "not-warranted disposition"
ALLOWED_CLASSIFICATIONS = {WARRANTED_FIX, NOT_WARRANTED_DISPOSITION}
CLASSIFICATION_CRITERIA = (
    "Security issues and bugs are warranted fixes; style preferences and alternative "
    "approaches are not-warranted dispositions."
)


@dataclass(frozen=True)
class ReviewThread:
    """Normalized review-thread data used to render the report."""

    path: str
    line: int | None
    url: str
    summary: str
    technical_concern: str
    classification: str | None = None
    justification: str | None = None


def _collapse_text(value: str) -> str:
    return " ".join(str(value).split()).strip()


def _summarize_text(value: str) -> str:
    text = _collapse_text(value)
    if not text:
        return "No summary provided."
    if len(text) <= 140:
        return text
    return f"{text[:137].rstrip()}..."


def _coerce_line(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _thread_label(thread: ReviewThread) -> str:
    if thread.line is None:
        return thread.path
    return f"{thread.path}:{thread.line}"


def _normalize_normalized_thread(raw_thread: dict[str, Any]) -> ReviewThread:
    url = _collapse_text(raw_thread.get("url", ""))
    if not url:
        raise ValueError("Each thread must include a direct GitHub URL.")

    summary = _collapse_text(raw_thread.get("summary", ""))
    concern = _collapse_text(raw_thread.get("technical_concern", "")) or summary
    if not concern:
        raise ValueError(f"Thread {url} is missing a technical concern.")

    classification = _collapse_text(raw_thread.get("classification", "")).lower() or None
    justification = _collapse_text(raw_thread.get("justification", "")) or None
    if classification is not None and classification not in ALLOWED_CLASSIFICATIONS:
        raise ValueError(
            "Classification must be one of: " f"{WARRANTED_FIX}, {NOT_WARRANTED_DISPOSITION}."
        )
    if classification is not None and justification is None:
        raise ValueError(f"Thread {url} includes a classification but no justification.")
    if classification is None and justification is not None:
        raise ValueError(f"Thread {url} includes a justification but no classification.")

    return ReviewThread(
        path=_collapse_text(raw_thread.get("path", "")) or "unknown-path",
        line=_coerce_line(raw_thread.get("line")),
        url=url,
        summary=_summarize_text(summary or concern),
        technical_concern=concern,
        classification=classification,
        justification=justification,
    )


def _normalize_graphql_thread(raw_thread: dict[str, Any]) -> ReviewThread:
    comments = raw_thread.get("comments", {})
    nodes = comments.get("nodes", []) if isinstance(comments, dict) else []
    first_comment = next((node for node in nodes if isinstance(node, dict)), None)
    if first_comment is None:
        raise ValueError("Each GraphQL review thread must include at least one comment node.")

    url = _collapse_text(first_comment.get("url", ""))
    if not url:
        raise ValueError("Each GraphQL review thread comment must include a URL.")

    concern = _collapse_text(first_comment.get("body", ""))
    if not concern:
        raise ValueError(f"Thread {url} is missing comment body text.")

    return ReviewThread(
        path=_collapse_text(raw_thread.get("path", "")) or "unknown-path",
        line=_coerce_line(raw_thread.get("line")),
        url=url,
        summary=_summarize_text(concern),
        technical_concern=concern,
    )


def _extract_pr_number(payload: dict[str, Any]) -> int | None:
    if isinstance(payload.get("pullRequest"), dict):
        return payload["pullRequest"].get("number")

    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    repository = data.get("repository")
    if not isinstance(repository, dict):
        return None
    pull_request = repository.get("pullRequest")
    if not isinstance(pull_request, dict):
        return None
    return pull_request.get("number")


def _extract_threads(payload: dict[str, Any]) -> list[ReviewThread]:
    if isinstance(payload.get("threads"), list):
        return [_normalize_normalized_thread(thread) for thread in payload["threads"]]

    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Unsupported payload shape. Expected `threads` or GitHub GraphQL `data`.")

    repository = data.get("repository")
    if not isinstance(repository, dict):
        raise ValueError("GitHub GraphQL payload is missing `data.repository`.")

    pull_request = repository.get("pullRequest")
    if not isinstance(pull_request, dict):
        raise ValueError("GitHub GraphQL payload is missing `data.repository.pullRequest`.")

    review_threads = pull_request.get("reviewThreads")
    if not isinstance(review_threads, dict):
        raise ValueError("GitHub GraphQL payload is missing `reviewThreads`.")

    nodes = review_threads.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("GitHub GraphQL payload is missing `reviewThreads.nodes`.")

    unresolved_threads = [
        _normalize_graphql_thread(thread)
        for thread in nodes
        if isinstance(thread, dict) and not bool(thread.get("isResolved"))
    ]
    if not unresolved_threads:
        raise ValueError("No unresolved review threads were found in the payload.")
    return unresolved_threads


def load_review_threads(path: str | Path) -> tuple[int | None, list[ReviewThread]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return _extract_pr_number(payload), _extract_threads(payload)


def render_report(pr_number: int | None, threads: list[ReviewThread], source_name: str) -> str:
    title_suffix = f"PR #{pr_number}" if pr_number is not None else "Pull Request"
    lines = [
        f"# {title_suffix} Unresolved Review Threads",
        "",
        f"Generated from `{source_name}`.",
        "",
        "## Classification Criteria",
        f"- {CLASSIFICATION_CRITERIA}",
        "",
    ]

    for index, thread in enumerate(threads, start=1):
        lines.extend(
            [
                f"## Thread {index}: `{_thread_label(thread)}`",
                f"- Direct link: {thread.url}",
                f"- Short summary: {thread.summary}",
                f"- Technical concern: {thread.technical_concern}",
                f"- Classification: {thread.classification or 'TBD'}",
                f"- Justification: {thread.justification or 'Pending classification.'}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, help="Path to the saved GitHub thread export JSON."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the rendered markdown report.",
    )
    parser.add_argument(
        "--require-count",
        type=int,
        default=None,
        help="Fail if the payload does not contain exactly this many unresolved threads.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pr_number, threads = load_review_threads(args.input)
    if args.require_count is not None and len(threads) != args.require_count:
        raise SystemExit(
            f"Expected {args.require_count} unresolved threads, found {len(threads)} in {args.input}."
        )

    report = render_report(pr_number, threads, Path(args.input).name)
    Path(args.output).write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
