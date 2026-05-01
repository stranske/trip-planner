"""Sanity checks for the cross-repo-smoke workflow file.

These keep the issue-#1045 workflow honest in case a future edit accidentally
drops the pinned ref, the dual checkout, or the live-tpp invocation. Run
with `pytest tests/scripts/test_cross_repo_smoke_workflow.py`.
"""

from __future__ import annotations

import importlib
import re
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "cross-repo-smoke.yml"
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
    assert env.get("TPP_OIDC_PROVIDER") in {"azure_ad", "google", "okta"}
    assert "--live-tpp required" in run_step["run"]


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACTIONLINT = _REPO_ROOT / ".workflows-lib" / "actionlint"


@pytest.mark.skipif(
    not _ACTIONLINT.is_file(), reason="actionlint binary not present in .workflows-lib/"
)
def test_workflow_passes_actionlint() -> None:
    result = subprocess.run(
        [str(_ACTIONLINT), str(WORKFLOW_PATH)],
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 0
    ), f"actionlint reported errors in {WORKFLOW_PATH.name}:\n{result.stdout}{result.stderr}"


# ---------------------------------------------------------------------------
# Contract-surface guard (AC#2)
#
# The cross-repo smoke job exercises the live planner ↔ TPP handshake.  The
# handshake depends on specific symbols exported from
# `trip_planner.integrations.tpp`.  If any symbol below is removed from
# `__init__.py` the import fails here *and* the full-product check script
# fails in CI — exactly the breakage detection AC#2 requires.
#
# Symbols are grouped by the planner service that imports them so the diff
# that broke the contract is easy to locate.
# ---------------------------------------------------------------------------

# Symbols consumed by trip_planner/app/services/proposal.py (submission path)
_PROPOSAL_SERVICE_SYMBOLS = [
    "BaseTPPIntegrationClient",
    "EvaluationResultIngestionError",
    "HTTPTPPIntegrationClient",
    "TPPCorrelationId",
    "TPPConfigurationError",
    "TPPContractError",
    "TPPErrorRecord",
    "TPPEvaluationResultIngestionService",
    "TPPExecutionStatus",
    "TPPProposalSubmissionService",
    "TPPRequestEnvelope",
    "TPPResponseEnvelope",
    "TPPRetryMetadata",
    "TPPTransportError",
]

# Symbols consumed by trip_planner/app/services/policy.py (policy-sync path)
_POLICY_SERVICE_SYMBOLS = [
    "BaseTPPIntegrationClient",
    "HTTPTPPIntegrationClient",
    "OrganizationContextSnapshot",
    "PolicyConstraintImport",
    "PolicyFreshness",
    "TPPPolicySyncService",
    "TPPRequestEnvelope",
    "TPPResponseEnvelope",
]


@pytest.mark.parametrize("symbol", sorted(set(_PROPOSAL_SERVICE_SYMBOLS + _POLICY_SERVICE_SYMBOLS)))
def test_tpp_integration_exports_required_symbol(symbol: str) -> None:
    """Each symbol must be importable from the public TPP integration package.

    A missing symbol breaks the planner services that depend on it, which in
    turn causes `make full-product-check --live-tpp required` to exit non-zero
    and fails the cross-repo-smoke CI job.
    """
    mod = importlib.import_module("trip_planner.integrations.tpp")
    assert hasattr(mod, symbol), (
        f"trip_planner.integrations.tpp is missing required cross-repo symbol '{symbol}'. "
        "Removing this export breaks the live planner-TPP handshake and will fail the "
        "cross-repo-smoke CI job."
    )
