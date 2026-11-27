"""Sanity checks for the cross-repo-smoke workflow file.

These keep the issue-#1045 workflow honest in case a future edit accidentally
drops the pinned ref, the dual checkout, or the live-tpp invocation. Run
with `pytest tests/scripts/test_cross_repo_smoke_workflow.py`.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.requirements import Requirement

from scripts import build_section15_receipt as receipts

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "cross-repo-smoke.yml"
)
GATE_WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "pr-00-gate.yml"
)
CI_GUIDE_PATH = Path(__file__).resolve().parents[2] / "docs" / "CROSS_REPO_SMOKE.md"
MAKEFILE_PATH = Path(__file__).resolve().parents[2] / "Makefile"


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


def _exact_ruff_pin(pyproject: Path) -> str:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    for raw in data["project"]["optional-dependencies"]["dev"]:
        req = Requirement(raw)
        if req.name != "ruff":
            continue
        for spec in req.specifier:
            if spec.operator == "==" and not spec.version.endswith(".*"):
                return spec.version
    raise AssertionError(f"no exact ruff pin in {pyproject}")


def test_workflow_pinned_ref_matches_offline_snapshot_and_planner_ruff(workflow: dict) -> None:
    """The smoke workflow pin must have a reviewed snapshot that agrees with planner pins."""
    repo_root = WORKFLOW_PATH.resolve().parents[2]
    pinned = workflow["env"]["TPP_PINNED_REF"]
    snapshot = repo_root / "tests/fixtures/tpp_dev_pins" / pinned / "pyproject.toml"
    assert snapshot.is_file(), f"missing offline TPP snapshot for workflow pin {pinned}"

    planner_ruff = _exact_ruff_pin(repo_root / "pyproject.toml")
    snapshot_ruff = _exact_ruff_pin(snapshot)
    assert planner_ruff == snapshot_ruff == "0.17.5"

    autofix = (repo_root / ".github/workflows/autofix-versions.env").read_text(encoding="utf-8")
    assert any(
        line.strip() == "RUFF_VERSION=0.17.5" for line in autofix.splitlines() if line.strip()
    )

    lock = (repo_root / "requirements.lock").read_text(encoding="utf-8")
    assert "ruff==0.17.5" in lock


def test_workflow_uses_single_top_level_tpp_pin_definition() -> None:
    workflow_text = WORKFLOW_PATH.read_text()
    workflow = yaml.safe_load(workflow_text)

    top_level_pin = workflow.get("env", {}).get("TPP_PINNED_REF")
    assert (
        isinstance(top_level_pin, str) and top_level_pin
    ), "TPP_PINNED_REF must be defined once at workflow-level env."
    assert (
        workflow_text.count("TPP_PINNED_REF:") == 1
    ), "Define TPP_PINNED_REF in a single top-level env line so pin bumps are one-line edits."


def test_workflow_call_declares_optional_cross_repo_token(workflow: dict) -> None:
    workflow_call = workflow.get(True, {}).get("workflow_call", {})
    secrets = workflow_call.get("secrets", {})

    assert secrets.get("CROSS_REPO_TOKEN") == {"required": False}


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

    planner_step = next(
        step for step in checkout_steps if step.get("with", {}).get("path") == "trip-planner"
    )
    assert "repository" not in planner_step.get(
        "with", {}
    ), "planner checkout should use the PR head repository via default actions/checkout behavior"

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

    assert "actions/setup-python@v6" in uses_values
    assert "actions/setup-node@v7" in uses_values
    assert "actions/setup-python@v5" not in uses_values
    assert "actions/setup-node@v6" not in uses_values


def test_cross_repo_smoke_job_uses_python_3_14(workflow: dict) -> None:
    """Cross-repo smoke must match the primary Python CI runtime (3.14)."""
    job = workflow["jobs"]["cross-repo-full-product"]
    setup = next(
        step
        for step in job["steps"]
        if step.get("name") == "Set up Python"
        and str(step.get("uses", "")).startswith("actions/setup-python@")
    )
    assert setup["with"]["python-version"] == "3.14"


def test_portal_contract_installs_both_projects_in_its_interpreter(workflow: dict) -> None:
    steps = workflow["jobs"]["cross-repo-full-product"]["steps"]
    contract = next(step for step in steps if step["name"] == "Verify TPP portal handoff contract")
    install = next(
        step for step in steps if step["name"] == "Install Travel-Plan-Permission dependencies"
    )
    pytest_line = next(line for line in contract["run"].splitlines() if " -m pytest " in line)
    test_python = shlex.split(pytest_line)[0]
    # Resolve the executable relative to each step's working directory: a pip
    # install in setup-python does not populate TPP's private test interpreter.
    test_python = (Path(contract["working-directory"]) / test_python).as_posix()
    commands = [
        shlex.split(line)
        for line in install["run"].splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    pip_installs = [cmd for cmd in commands if cmd[1:5] == ["-m", "pip", "install", "-e"]]
    assert pip_installs, "contract environment needs an explicit project dependency install"
    command = pip_installs[0]
    install_python = (Path(install["working-directory"]) / command[0]).as_posix()
    # pathlib does not collapse '..'; compare canonical lexical workspace paths.
    assert (Path("/workspace") / test_python).resolve() == (
        Path("/workspace") / install_python
    ).resolve()
    assert ".[dev]" in command, "TPP runtime and test dependencies are required"
    assert (
        "../trip-planner[dev]" in command
    ), "planner runtime and test dependencies must reach TPP Python"
    assert "||" not in command, "failed complete installation must not fall back to runtime-only"
    assert [command[0], "-m", "pip", "check"] in commands
    assert steps.index(install) < steps.index(contract)


def test_workflow_checks_live_dev_pins_before_joint_install(workflow: dict) -> None:
    """The pin guard must inspect the live checkout before pip can hit #1973."""
    steps = workflow["jobs"]["cross-repo-full-product"]["steps"]
    guard = next(
        step for step in steps if step["name"] == "Check dev pins co-resolve with pinned TPP"
    )
    planner_install = next(
        step for step in steps if step["name"] == "Install trip-planner backend dependencies"
    )
    joint_install = next(
        step for step in steps if step["name"] == "Install Travel-Plan-Permission dependencies"
    )

    assert guard["working-directory"] == "trip-planner"
    assert guard["env"]["TPP_REPO_PATH"] == "../Travel-Plan-Permission"
    assert shlex.split(guard["run"]) == [
        "python",
        "-m",
        "pytest",
        "tests/scripts/test_cross_repo_dev_pins.py",
        "-q",
    ]
    assert steps.index(planner_install) < steps.index(guard) < steps.index(joint_install)


def test_workflow_runs_full_product_check_with_repo_path(workflow: dict) -> None:
    job = workflow["jobs"]["cross-repo-full-product"]
    run_step = next(
        step for step in job["steps"] if "make full-product-check" in str(step.get("run", ""))
    )
    env = run_step.get("env", {})
    assert env.get("TPP_REPO_PATH") == "../Travel-Plan-Permission"
    assert env.get("TPP_OIDC_PROVIDER") in {"azure_ad", "google", "okta"}
    assert env.get("LIVE_TPP") == "required"
    assert "make full-product-check" in run_step["run"]


def test_workflow_logs_pinned_and_resolved_tpp_sha(workflow: dict) -> None:
    job = workflow["jobs"]["cross-repo-full-product"]
    log_step = next(
        step for step in job["steps"] if step.get("name") == "Log resolved pinned TPP SHA"
    )
    run_script = str(log_step.get("run", ""))
    assert "TPP_PINNED_REF=${TPP_PINNED_REF}" in run_script
    assert "git rev-parse HEAD" in run_script


def test_gate_summary_requires_cross_repo_smoke_job() -> None:
    gate = yaml.safe_load(GATE_WORKFLOW_PATH.read_text())
    jobs = gate["jobs"]

    assert jobs["cross-repo-smoke"]["uses"] == "./.github/workflows/cross-repo-smoke.yml"
    assert "cross-repo-smoke" in jobs["summary"]["needs"]


def test_gate_summary_reports_required_gate_status_context() -> None:
    gate_text = GATE_WORKFLOW_PATH.read_text()

    assert "CROSS_REPO_RESULT" in gate_text
    assert "Cross-repo smoke check failed" in gate_text
    assert re.search(
        r"createCommitStatus\s*\(.*?context\s*:\s*['\"]Gate / gate['\"]",
        gate_text,
        re.DOTALL,
    )


def test_ci_guide_matches_make_full_product_check_contract() -> None:
    guide = CI_GUIDE_PATH.read_text()
    makefile = MAKEFILE_PATH.read_text()

    assert "make full-product-check" in guide
    assert "TPP_REPO_PATH=../Travel-Plan-Permission" in guide
    assert "python scripts/check_full_product_verification.py --live-tpp=$(LIVE_TPP)" in makefile


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACTIONLINT = _REPO_ROOT / ".workflows-lib" / "actionlint"


@pytest.fixture
def actionlint() -> str:
    if os.environ.get("TRIP_PLANNER_REQUIRE_ACTIONLINT") == "1":
        executable = shutil.which("actionlint")
        if executable is None:
            pytest.fail("required actionlint missing from PATH")
        return executable
    if _ACTIONLINT.is_file():
        return str(_ACTIONLINT)
    return shutil.which("actionlint") or pytest.skip(
        "actionlint not found (checked .workflows-lib/actionlint and PATH)"
    )


def test_workflow_passes_actionlint(actionlint: str) -> None:
    result = subprocess.run(
        [actionlint, str(WORKFLOW_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert (
        result.returncode == 0
    ), f"actionlint reported errors in {WORKFLOW_PATH.name}:\n{result.stdout}{result.stderr}"


def test_actionlint_rejects_invalid_workflow(actionlint: str, tmp_path: Path) -> None:
    invalid = tmp_path / WORKFLOW_PATH.name
    invalid.write_bytes(WORKFLOW_PATH.read_bytes() + b"\nunexpected-root-key: true\n")
    result = subprocess.run([actionlint, str(invalid)], capture_output=True, text=True)
    assert result.returncode == 1, result
    assert 'unexpected key "unexpected-root-key"' in result.stdout, result


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


# --- Section 15 execution receipts (issue #2066) ---------------------------------


_CONSUMER = "a" * 40
_PRODUCER = "b" * 40
_RUN = "https://github.com/stranske/trip-planner/actions/runs/123"
_ARTIFACT = _RUN + "/artifacts/456"


def _steps(workflow: dict) -> list[dict]:
    return workflow["jobs"]["cross-repo-full-product"]["steps"]


def _step(workflow: dict, name: str) -> dict:
    return next(step for step in _steps(workflow) if step.get("name") == name)


def test_workflow_publishes_section15_receipts_after_same_run_evidence(
    workflow: dict,
) -> None:
    steps = _steps(workflow)
    shas = _step(workflow, "Log resolved pinned TPP SHA")
    evidence = _step(workflow, "Upload section-15 evidence")
    build = _step(workflow, "Build section-15 execution receipts")
    publish = _step(workflow, "Upload section-15 execution receipts")

    assert shas["id"] == "checkout_shas"
    assert 'producer_sha=$(git rev-parse HEAD)" >> "$GITHUB_OUTPUT"' in shas["run"]
    assert (
        'consumer_sha=$(git -C ../trip-planner rev-parse HEAD)" >> "$GITHUB_OUTPUT"' in shas["run"]
    )
    assert evidence["id"] == "section15_evidence"
    assert evidence["with"]["name"] == "section-15-evidence"
    assert evidence["with"]["path"] == "${{ env.SECTION15_EVIDENCE_DIR }}"
    assert publish["with"]["name"] == "section-15-execution-receipts"
    assert publish["with"]["path"] == "${{ env.SECTION15_RECEIPTS_DIR }}"
    assert publish["with"]["if-no-files-found"] == "error"
    for step in (evidence, build, publish):
        assert step["if"] == "${{ !cancelled() }}", step["name"]
    assert steps.index(evidence) < steps.index(build) < steps.index(publish)

    env = build["env"]
    assert env["CONSUMER_SHA"] == "${{ steps.checkout_shas.outputs.consumer_sha }}"
    assert env["PRODUCER_SHA"] == "${{ steps.checkout_shas.outputs.producer_sha }}"
    # The evidence locator is the URL returned by this run's upload step.
    assert env["ARTIFACT_URL"] == "${{ steps.section15_evidence.outputs.artifact-url }}"
    assert env["RUN_URL"] == (
        "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
    )
    run = build["run"]
    assert "--layer pinned_two_app" in run and "--layer configured_full_product" in run
    assert "$SECTION15_RECEIPTS_DIR/pinned_two_app.json" in run
    assert "$SECTION15_RECEIPTS_DIR/configured_full_product.json" in run


def test_workflow_captures_pinned_two_app_result_with_recorded_command(
    workflow: dict,
) -> None:
    contract = _step(workflow, "Verify TPP portal handoff contract")
    lines = [line.strip() for line in contract["run"].splitlines()]
    pytest_line = next(line for line in lines if " -m pytest " in line)
    assert pytest_line.startswith(receipts.PINNED_TWO_APP_COMMAND + " --junitxml=")
    assert '"$SECTION15_EVIDENCE_DIR/pinned_two_app.junit.xml"' in pytest_line
    assert pytest_line.endswith("|| status=$?")
    # The job still fails on a failed pinned two-app run.
    assert lines[-1] == 'exit "$status"'
    assert 'echo "$status" > "$SECTION15_EVIDENCE_DIR/pinned_two_app.exit_code"' in lines


def test_workflow_full_product_writes_strict_result_into_evidence(
    workflow: dict,
) -> None:
    run_step = _step(workflow, "Run full-product-check against sibling TPP checkout")
    assert run_step["env"]["FULL_PRODUCT_RESULT_JSON"] == (
        "${{ env.SECTION15_EVIDENCE_DIR }}/configured_full_product.result.json"
    )
    makefile = MAKEFILE_PATH.read_text()
    assert receipts.CONFIGURED_FULL_PRODUCT_COMMAND.replace("required", "$(LIVE_TPP)") in makefile


def _junit(path: Path, *, tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> Path:
    path.write_text(
        f'<testsuites><testsuite name="pytest" tests="{tests}" failures="{failures}" '
        f'errors="{errors}" skipped="{skipped}"/></testsuites>',
        encoding="utf-8",
    )
    return path


def _two_app(tmp_path: Path, **overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "layer": "pinned_two_app",
        "consumer_sha": _CONSUMER,
        "producer_sha": _PRODUCER,
        "run_url": _RUN,
        "artifact_url": _ARTIFACT,
        "environment_text": "env",
        "junit_xml": _junit(tmp_path / "junit.xml", tests=3),
        "pytest_exit_code": 0,
    }
    kwargs.update(overrides)
    return receipts.build_receipt(**kwargs)


def test_pinned_two_app_receipt_records_actual_counts(tmp_path: Path) -> None:
    receipt = _two_app(tmp_path)
    observed = receipt["observed_result"]
    assert observed["status"] == "PASS"
    assert observed["skipped"] == 0
    assert (observed["passed"], observed["tests"]) == (3, 3)
    assert (
        observed["summary"] == "3 passed, 0 failed, 0 errors, 0 skipped of 3 pinned two-app tests"
    )
    assert "ineligible_reasons" not in observed
    assert receipt["command"] == receipts.PINNED_TWO_APP_COMMAND
    assert (receipt["consumer_sha"], receipt["producer_sha"]) == (_CONSUMER, _PRODUCER)
    assert (receipt["run"], receipt["artifact"]) == (_RUN, _ARTIFACT)


@pytest.mark.parametrize(
    "case, expected_status, reason",
    [
        ("skipped", "SKIPPED", "pytest skipped required tests"),
        ("failed", "FAIL", "pytest reported failures or errors"),
        ("no-tests", "FAIL", "pytest collected no tests"),
        ("missing-report", "MISSING", "pinned two-app pytest report missing"),
        ("missing-exit-code", "FAIL", "pytest exit code None"),
        ("short-sha", "INELIGIBLE", "consumer_sha is not a full 40-character SHA"),
        ("other-run", "INELIGIBLE", "evidence artifact does not belong to this run"),
        (
            "no-artifact",
            "INELIGIBLE",
            "evidence artifact URL is missing or not an Actions artifact URL",
        ),
    ],
)
def test_pinned_two_app_receipt_fails_closed(
    tmp_path: Path, case: str, expected_status: str, reason: str
) -> None:
    junit = tmp_path / "j.xml"
    cases: dict[str, Callable[[], dict[str, Any]]] = {
        "skipped": lambda: {"junit_xml": _junit(junit, tests=3, skipped=1)},
        "failed": lambda: {
            "junit_xml": _junit(junit, tests=3, failures=1),
            "pytest_exit_code": 1,
        },
        "no-tests": lambda: {
            "junit_xml": _junit(junit, tests=0),
            "pytest_exit_code": 5,
        },
        "missing-report": lambda: {"junit_xml": tmp_path / "absent.xml"},
        "missing-exit-code": lambda: {"pytest_exit_code": None},
        "short-sha": lambda: {"consumer_sha": "abc1234"},
        "other-run": lambda: {"artifact_url": _RUN[:-3] + "999/artifacts/456"},
        "no-artifact": lambda: {"artifact_url": ""},
    }
    overrides = cases[case]()
    observed = _two_app(tmp_path, **overrides)["observed_result"]
    assert observed["status"] == expected_status
    assert reason in observed["ineligible_reasons"]


def _full_product_checks(names: list[str], *, status: str = "PASS") -> list[dict[str, str]]:
    return [{"name": name, "status": status} for name in names]


def _configured(tmp_path: Path, result: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    kwargs: dict[str, Any] = {
        "layer": "configured_full_product",
        "consumer_sha": _CONSUMER,
        "producer_sha": _PRODUCER,
        "run_url": _RUN,
        "artifact_url": _ARTIFACT,
        "environment_text": "env",
        "result_json": path,
    }
    kwargs.update(overrides)
    return receipts.build_receipt(**kwargs)


def _passing_full_product_result(**overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "PASS",
        "exit_code": 0,
        "command": receipts.CONFIGURED_FULL_PRODUCT_COMMAND,
        "required_checks": _full_product_checks(list(receipts.FULL_PRODUCT_REQUIRED_CHECK_NAMES)),
    }
    result.update(overrides)
    return result


def test_configured_full_product_receipt_passes_with_complete_checks(tmp_path: Path) -> None:
    observed = _configured(tmp_path, _passing_full_product_result())["observed_result"]
    assert observed["status"] == "PASS"
    assert "ineligible_reasons" not in observed


@pytest.mark.parametrize(
    "case, reason",
    [
        (
            "missing-name",
            "required check missing: live-tpp",
        ),
        ("duplicate-name", "duplicate required check name: live-tpp"),
        ("unknown-name", "unknown required check name: extra-check"),
    ],
)
def test_configured_full_product_receipt_rejects_incomplete_check_set(
    tmp_path: Path, case: str, reason: str
) -> None:
    names = list(receipts.FULL_PRODUCT_REQUIRED_CHECK_NAMES)
    if case == "missing-name":
        names = names[:-1]
    elif case == "duplicate-name":
        names = names + ["live-tpp"]
    elif case == "unknown-name":
        names = names + ["extra-check"]
    observed = _configured(
        tmp_path,
        _passing_full_product_result(
            required_checks=_full_product_checks(names),
        ),
    )["observed_result"]
    assert observed["status"] == "INELIGIBLE"
    assert reason in observed["ineligible_reasons"]


def test_configured_full_product_receipt_ineligible_when_command_omitted(
    tmp_path: Path,
) -> None:
    receipt = _configured(
        tmp_path,
        _passing_full_product_result(command=""),
    )
    observed = receipt["observed_result"]
    assert observed["status"] == "INELIGIBLE"
    assert "strict result recorded no command" in observed["ineligible_reasons"]
    assert receipt["command"] == receipts.CONFIGURED_FULL_PRODUCT_COMMAND


def test_receipt_builder_cli_writes_configured_receipt_without_result(
    tmp_path: Path,
) -> None:
    output = tmp_path / "receipts" / "configured_full_product.json"
    assert (
        receipts.main(
            [
                "--layer=configured_full_product",
                f"--consumer-sha={_CONSUMER}",
                f"--producer-sha={_PRODUCER}",
                f"--run-url={_RUN}",
                f"--artifact-url={_ARTIFACT}",
                f"--result-json={tmp_path / 'absent.json'}",
                f"--output={output}",
            ]
        )
        == 0
    )
    receipt = json.loads(output.read_text())
    assert receipt["command"] == receipts.CONFIGURED_FULL_PRODUCT_COMMAND
    assert receipt["observed_result"]["status"] == "MISSING"
    assert receipt["observed_result"]["skipped"] is None
    assert receipt["environment"].startswith("GitHub Actions ubuntu-latest runner, CPython ")
    for boundary in (
        "127.0.0.1 loopback HTTP",
        "SQLite",
        "no managed LLM",
        "not hosted",
    ):
        assert boundary in receipt["environment"]
