import json

import pytest

import scripts.render_pr_review_thread_report as report


def test_load_review_threads_supports_graphql_payload(tmp_path):
    payload = {
        "data": {
            "repository": {
                "pullRequest": {
                    "number": 569,
                    "reviewThreads": {
                        "nodes": [
                            {
                                "isResolved": False,
                                "path": "trip_planner/planner.py",
                                "line": 47,
                                "comments": {
                                    "nodes": [
                                        {
                                            "url": "https://github.com/stranske/trip-planner/pull/569#discussion_r1",
                                            "body": "This branch can return stale fallback data when the source feed is empty.",
                                        }
                                    ]
                                },
                            },
                            {
                                "isResolved": True,
                                "path": "ignored.py",
                                "line": 1,
                                "comments": {
                                    "nodes": [
                                        {"url": "https://example.com", "body": "ignore"}
                                    ]
                                },
                            },
                        ]
                    },
                }
            }
        }
    }
    input_path = tmp_path / "threads.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    pr_number, threads = report.load_review_threads(input_path)

    assert pr_number == 569
    assert threads == [
        report.ReviewThread(
            path="trip_planner/planner.py",
            line=47,
            url="https://github.com/stranske/trip-planner/pull/569#discussion_r1",
            summary="This branch can return stale fallback data when the source feed is empty.",
            technical_concern="This branch can return stale fallback data when the source feed is empty.",
            classification=None,
            justification=None,
        )
    ]


def test_render_report_preserves_manual_classification():
    rendered = report.render_report(
        569,
        [
            report.ReviewThread(
                path="scripts/example.py",
                line=12,
                url="https://github.com/stranske/trip-planner/pull/569#discussion_r2",
                summary="Guard missing file existence checks before dereferencing.",
                technical_concern="Guard missing file existence checks before dereferencing.",
                classification="warranted fix",
                justification="Potential runtime failure when the fixture is absent.",
            )
        ],
        "threads.json",
    )

    assert "# PR #569 Unresolved Review Threads" in rendered
    assert "## Classification Criteria" in rendered
    assert report.CLASSIFICATION_CRITERIA in rendered
    assert "- Classification: warranted fix" in rendered
    assert (
        "- Justification: Potential runtime failure when the fixture is absent."
        in rendered
    )


def test_load_review_threads_accepts_supported_classifications(tmp_path):
    payload = {
        "pullRequest": {"number": 569},
        "threads": [
            {
                "path": "scripts/example.py",
                "line": 12,
                "url": "https://github.com/stranske/trip-planner/pull/569#discussion_r2",
                "summary": "Summary",
                "technical_concern": "Concern",
                "classification": "not-warranted disposition",
                "justification": "Alternative implementation preference, not a functional defect.",
            }
        ],
    }
    input_path = tmp_path / "threads.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    _, threads = report.load_review_threads(input_path)

    assert threads[0].classification == "not-warranted disposition"
    assert (
        threads[0].justification
        == "Alternative implementation preference, not a functional defect."
    )


def test_load_review_threads_rejects_unknown_classification(tmp_path):
    payload = {
        "pullRequest": {"number": 569},
        "threads": [
            {
                "path": "scripts/example.py",
                "line": 12,
                "url": "https://github.com/stranske/trip-planner/pull/569#discussion_r2",
                "summary": "Summary",
                "technical_concern": "Concern",
                "classification": "needs discussion",
                "justification": "Not part of the supported classification criteria.",
            }
        ],
    }
    input_path = tmp_path / "threads.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Classification must be one of"):
        report.load_review_threads(input_path)


def test_load_review_threads_requires_justification_for_classification(tmp_path):
    payload = {
        "pullRequest": {"number": 569},
        "threads": [
            {
                "path": "scripts/example.py",
                "line": 12,
                "url": "https://github.com/stranske/trip-planner/pull/569#discussion_r2",
                "summary": "Summary",
                "technical_concern": "Concern",
                "classification": "warranted fix",
            }
        ],
    }
    input_path = tmp_path / "threads.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        ValueError, match="includes a classification but no justification"
    ):
        report.load_review_threads(input_path)


def test_main_fails_when_required_thread_count_is_wrong(tmp_path):
    payload = {
        "pullRequest": {"number": 569},
        "threads": [
            {
                "path": "scripts/example.py",
                "line": 12,
                "url": "https://github.com/stranske/trip-planner/pull/569#discussion_r2",
                "summary": "Summary",
                "technical_concern": "Concern",
            }
        ],
    }
    input_path = tmp_path / "threads.json"
    output_path = tmp_path / "report.md"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SystemExit, match="Expected 5 unresolved threads, found 1"):
        report.main(
            [
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--require-count",
                "5",
            ]
        )
