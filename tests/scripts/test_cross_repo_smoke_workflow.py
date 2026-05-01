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
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "cross-repo-smoke.yml"
)
GATE_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "pr-00-gate.yml"
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


def test_workflow_call_declares_optional_cross_repo_token(workflow: dict) -> None:
    workflow_call = workflow.get(True, {}).get("workflow_call", {})
    secrets = workflow_call.get("secrets", {})

    assert secrets.get("CROSS_REPO_TOKEN") == {"required": False}


def test_workflow_checks_out_both_repos(workflow: dict) -> None:
    job = workflow["jobs"]["cross-repo-full-product"]
    checkout_steps = [
        step
        for step in job["steps"]
        if isinstance(step.get("uses"), str)
        and step["uses"].startswith("actions/checkout@")
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
    assert "CROSS_REPO_TOKEN" in str(with_block.get("token", ""))


def test_workflow_uses_stable_setup_action_tags(workflow: dict) -> None:
    job = workflow["jobs"]["cross-repo-full-product"]
    uses_values = [str(step.get("uses", "")) for step in job["steps"]]

    assert "actions/setup-python@v5" in uses_values
    assert "actions/setup-node@v4" in uses_values
    assert "actions/setup-python@v6" not in uses_values
    assert "actions/setup-node@v6" not in uses_values


def test_workflow_runs_full_product_check_with_repo_path(workflow: dict) -> None:
    job = workflow["jobs"]["cross-repo-full-product"]
    run_step = next(
        step
        for step in job["steps"]
        if "make full-product-check" in str(step.get("run", ""))
    )
    env = run_step.get("env", {})
    assert env.get("TPP_REPO_PATH") == "../Travel-Plan-Permission"
    assert env.get("TPP_OIDC_PROVIDER") in {"azure_ad", "google", "okta"}
    assert env.get("LIVE_TPP") == "required"
    assert "make full-product-check" in run_step["run"]


def test_gate_summary_requires_cross_repo_smoke_job() -> None:
    gate = yaml.safe_load(GATE_WORKFLOW_PATH.read_text())
    jobs = gate["jobs"]

    assert (
        jobs["cross-repo-smoke"]["uses"] == "./.github/workflows/cross-repo-smoke.yml"
    )
    assert "cross-repo-smoke" in jobs["summary"]["needs"]


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
    assert result.returncode == 0, (
        f"actionlint reported errors in {WORKFLOW_PATH.name}:\n{result.stdout}{result.stderr}"
    )


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


@pytest.mark.parametrize(
    "symbol", sorted(set(_PROPOSAL_SERVICE_SYMBOLS + _POLICY_SERVICE_SYMBOLS))
)
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


# ---------------------------------------------------------------------------
# Client method guards (AC#2 — method-level surface)
#
# The cross-repo handshake depends on specific methods of BaseTPPIntegrationClient
# and HTTPTPPIntegrationClient.  Removing `submit_proposal` (or any method below)
# from the client class — even if the class itself remains exported — breaks the
# TPP dispatch path and causes `full-product-check --live-tpp required` to fail.
# ---------------------------------------------------------------------------

# Operations that form the cross-repo dispatch contract.
# Grouped to match the four TPP workflow phases: policy-sync, submission,
# result-ingestion, and status-poll.
_CLIENT_CONTRACT_METHODS = [
    "fetch_policy_constraints",  # policy-sync path
    "submit_proposal",  # submission path (mentioned in AC#2)
    "fetch_evaluation_result",  # result-ingestion path
    "poll_execution_status",  # status-poll path
]


@pytest.mark.parametrize("method_name", _CLIENT_CONTRACT_METHODS)
def test_base_client_exposes_contract_method(method_name: str) -> None:
    """BaseTPPIntegrationClient must expose every dispatch method.

    Removing any of these breaks the planner → TPP handshake and fails the
    cross-repo-smoke CI job (AC#2 failure-mode guard).
    """
    mod = importlib.import_module("trip_planner.integrations.tpp")
    cls = mod.BaseTPPIntegrationClient
    assert callable(getattr(cls, method_name, None)), (
        f"BaseTPPIntegrationClient.{method_name} is missing or not callable. "
        "This breaks the cross-repo dispatch contract and will fail the smoke job."
    )


@pytest.mark.parametrize("method_name", _CLIENT_CONTRACT_METHODS)
def test_http_client_exposes_contract_method(method_name: str) -> None:
    """HTTPTPPIntegrationClient must expose every dispatch method.

    The HTTP client is the concrete implementation used in production and in
    the full-product-check subprocess; a missing method causes an AttributeError
    at runtime and exits the smoke job non-zero.
    """
    mod = importlib.import_module("trip_planner.integrations.tpp")
    cls = mod.HTTPTPPIntegrationClient
    assert callable(getattr(cls, method_name, None)), (
        f"HTTPTPPIntegrationClient.{method_name} is missing or not callable. "
        "This breaks the live cross-repo handshake and will fail the smoke job."
    )
