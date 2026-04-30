"""Sanity checks for the cross-repo-smoke workflow file.

These keep the issue-#1045 workflow honest in case a future edit accidentally
drops the pinned ref, the dual checkout, or the live-tpp invocation. Run
with `pytest tests/scripts/test_cross_repo_smoke_workflow.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "cross-repo-smoke.yml"
)


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text())


def test_workflow_file_exists() -> None:
    assert WORKFLOW_PATH.is_file(), f"missing workflow file at {WORKFLOW_PATH}"


def test_workflow_defines_cross_repo_full_product_job(workflow: dict) -> None:
    jobs = workflow.get("jobs", {})
    assert "cross-repo-full-product" in jobs, jobs.keys()


def test_workflow_pins_tpp_ref(workflow: dict) -> None:
    env = workflow.get("env", {})
    pinned = env.get("TPP_PINNED_REF", "")
    assert re.fullmatch(r"[0-9a-f]{40}", pinned), pinned


def test_workflow_checks_out_both_repos(workflow: dict) -> None:
    job = workflow["jobs"]["cross-repo-full-product"]
    checkout_steps = [
        step
        for step in job["steps"]
        if isinstance(step.get("uses"), str) and step["uses"].startswith("actions/checkout@")
    ]
    paths = [step.get("with", {}).get("path") for step in checkout_steps]
    assert "trip-planner" in paths, paths
    assert "Travel-Plan-Permission" in paths, paths

    tpp_step = next(
        step
        for step in checkout_steps
        if step.get("with", {}).get("path") == "Travel-Plan-Permission"
    )
    with_block = tpp_step["with"]
    assert with_block.get("repository") == "stranske/Travel-Plan-Permission"
    assert "${{ env.TPP_PINNED_REF }}" in str(with_block.get("ref", ""))


def test_workflow_runs_full_product_check_with_repo_path(workflow: dict) -> None:
    job = workflow["jobs"]["cross-repo-full-product"]
    run_step = next(
        step
        for step in job["steps"]
        if "scripts/check_full_product_verification.py" in str(step.get("run", ""))
    )
    env = run_step.get("env", {})
    assert "${{ github.workspace }}/Travel-Plan-Permission" in str(env.get("TPP_REPO_PATH", ""))
    assert "--live-tpp required" in run_step["run"]
