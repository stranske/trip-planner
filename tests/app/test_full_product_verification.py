import json
import os
import subprocess
from typing import Any

from scripts import check_full_product_verification as verifier
from scripts.check_full_product_verification import (
    CheckResult,
    classify_map_prerequisite,
    classify_planner_llm_prerequisite,
    run_frontend_runtime_smoke,
    run_product_journeys,
    tpp_prerequisite_status,
)


def test_full_product_local_journeys_cover_runtime_identifiers(monkeypatch) -> None:
    for name in (
        "TPP_BASE_URL",
        "TPP_ACCESS_TOKEN",
        "TPP_OIDC_PROVIDER",
        "TPP_REPO_PATH",
        "TRIP_PLANNER_DATA_ZONE",
        "TRIP_PLANNER_OPENAI_AUTHORIZED_ENDPOINT",
        "TRIP_PLANNER_PLANNER_MODEL_PROVIDER",
        "TRIP_PLANNER_PLANNER_MODEL",
        "OPENAI_API_KEY",
        "VITE_GOOGLE_MAPS_PROVIDER_STATE",
        "VITE_GOOGLE_MAPS_BROWSER_API_KEY",
        "VITE_GOOGLE_MAPS_EMBED_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    checks = run_product_journeys(live_tpp="off")
    by_name = {check.name: check for check in checks}

    assert by_name["local-leisure-journey"].status == "PASS"
    assert by_name["local-business-journey"].status == "PASS"
    assert by_name["live-tpp"].status == "SKIPPED"
    assert by_name["live-tpp"].details["mode"] == "off"
    assert "remediation" in by_name["live-tpp"].details
    assert by_name["local-leisure-journey"].details["trip_id"].startswith("trip-")
    assert by_name["local-leisure-journey"].details["scenario_id"].startswith("scenario:")
    assert by_name["local-leisure-journey"].details["route_contexts"] > 0
    assert by_name["local-leisure-journey"].details["planner_runtime"] in {
        "fallback",
        "model",
    }
    assert by_name["local-business-journey"].details["proposal_id"].startswith("proposal:trip-")
    assert by_name["local-business-journey"].details["evaluation_status"] == "non_compliant"
    assert by_name["local-business-journey"].details["follow_up_status"] == "no_scenario_lineage"
    assert by_name["local-business-journey"].details["status_poll"] in {
        "deferred",
        "failed",
        "retry_scheduled",
    }
    assert "TRIP_PLANNER_DATABASE_URL" not in os.environ


def test_map_provider_check_reports_missing_config_as_skipped(monkeypatch) -> None:
    for name in (
        "VITE_GOOGLE_MAPS_PROVIDER_STATE",
        "VITE_GOOGLE_MAPS_BROWSER_API_KEY",
        "VITE_GOOGLE_MAPS_EMBED_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    check = classify_map_prerequisite()

    assert check.status == "SKIPPED"
    assert check.details["provider_state"] == "fallback"
    assert check.details["missing_env"] == "VITE_GOOGLE_MAPS_BROWSER_API_KEY"


def test_map_provider_check_fails_when_configured_provider_errors(monkeypatch) -> None:
    monkeypatch.setenv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key")
    monkeypatch.setenv("VITE_GOOGLE_MAPS_PROVIDER_STATE", "error")

    check = classify_map_prerequisite()

    assert check.status == "FAIL"
    assert check.details["provider_state"] == "error"


def test_planner_llm_check_blocks_openai_in_proprietary_zone_without_marker() -> None:
    check = classify_planner_llm_prerequisite(
        env={
            "TRIP_PLANNER_DATA_ZONE": "proprietary",
            "TRIP_PLANNER_PLANNER_MODEL_PROVIDER": "openai",
            "TRIP_PLANNER_PLANNER_MODEL": "gpt-test",
            "OPENAI_API_KEY": "fake-key",
        }
    )

    assert check.status == "BLOCKED"
    assert check.details["data_zone"] == "proprietary"
    assert check.details["llm_status"] == "blocked"
    assert check.details["fallback_reason"] == "proprietary_zone_llm_blocked"


def test_planner_llm_check_reports_authorized_openai_ready() -> None:
    check = classify_planner_llm_prerequisite(
        env={
            "TRIP_PLANNER_DATA_ZONE": "proprietary",
            "TRIP_PLANNER_OPENAI_AUTHORIZED_ENDPOINT": "1",
            "TRIP_PLANNER_PLANNER_MODEL_PROVIDER": "openai",
            "TRIP_PLANNER_PLANNER_MODEL": "gpt-test",
            "OPENAI_API_KEY": "fake-key",
        }
    )

    assert check.status == "READY"
    assert check.details["data_zone"] == "proprietary"
    assert check.details["llm_status"] == "authorized"


def test_live_tpp_auto_reports_missing_config_as_skipped(monkeypatch, tmp_path) -> None:
    for name in (
        "TPP_BASE_URL",
        "TPP_ACCESS_TOKEN",
        "TPP_OIDC_PROVIDER",
        "TPP_REPO_PATH",
    ):
        monkeypatch.delenv(name, raising=False)

    check = tpp_prerequisite_status(live_tpp="auto", default_repo_path=tmp_path / "missing")

    assert check.status == "SKIPPED"
    assert check.details["missing_env"] == "TPP_BASE_URL or TPP_REPO_PATH"
    assert check.details["default_repo_path"] == str(tmp_path / "missing")
    assert "TPP_BASE_URL" in check.details["remediation"]
    assert "TPP_REPO_PATH" in check.details["remediation"]


def test_live_tpp_auto_reports_ready_with_base_url_and_auth_config() -> None:
    check = tpp_prerequisite_status(
        live_tpp="auto",
        env={
            "TPP_BASE_URL": "https://tpp.example.test",
            "TPP_ACCESS_TOKEN": "token",
            "TPP_OIDC_PROVIDER": "google",
        },
    )

    assert check.status == "READY"
    assert check.details["TPP_BASE_URL"] == "https://tpp.example.test"


def test_live_tpp_auto_skips_when_auth_exists_without_transport_target(tmp_path) -> None:
    check = tpp_prerequisite_status(
        live_tpp="auto",
        default_repo_path=tmp_path / "missing",
        env={
            "TPP_ACCESS_TOKEN": "token",
            "TPP_OIDC_PROVIDER": "google",
        },
    )

    assert check.status == "SKIPPED"
    assert check.details["missing_env"] == "TPP_BASE_URL or TPP_REPO_PATH"
    assert check.details["default_repo_path"] == str(tmp_path / "missing")
    assert "remediation" in check.details


def test_live_tpp_auto_reports_invalid_repo_path_as_blocked(tmp_path) -> None:
    missing_repo = tmp_path / "missing-tpp"

    check = tpp_prerequisite_status(
        live_tpp="auto",
        env={
            "TPP_ACCESS_TOKEN": "token",
            "TPP_OIDC_PROVIDER": "google",
            "TPP_REPO_PATH": str(missing_repo),
        },
    )

    assert check.status == "BLOCKED"
    assert check.details["invalid_path"] == {"TPP_REPO_PATH": str(missing_repo)}
    assert check.details["invalid_path_detail"]["kind"] == "missing"
    assert check.details["invalid_path_detail"]["path"] == str(missing_repo)
    assert "TPP_REPO_PATH" in check.details["remediation"]


def test_live_tpp_blocked_distinguishes_repo_path_that_is_a_file(tmp_path) -> None:
    file_path = tmp_path / "not-a-checkout"
    file_path.write_text("", encoding="utf-8")

    check = tpp_prerequisite_status(
        live_tpp="auto",
        env={
            "TPP_ACCESS_TOKEN": "token",
            "TPP_OIDC_PROVIDER": "google",
            "TPP_REPO_PATH": str(file_path),
        },
    )

    assert check.status == "BLOCKED"
    assert check.details["invalid_path_detail"]["kind"] == "not-a-directory"
    assert check.details["invalid_path_detail"]["path"] == str(file_path)
    assert "not a directory" in check.details["invalid_path_detail"]["message"]


def test_live_tpp_blocked_reports_missing_auth_with_remediation(tmp_path) -> None:
    check = tpp_prerequisite_status(
        live_tpp="auto",
        env={"TPP_BASE_URL": "https://tpp.example.test"},
    )

    assert check.status == "BLOCKED"
    assert "TPP_ACCESS_TOKEN" in check.details["missing_env"]
    assert "TPP_OIDC_PROVIDER" in check.details["missing_env"]
    assert "TPP_ACCESS_TOKEN" in check.details["remediation"]


def test_live_tpp_off_reports_actionable_remediation() -> None:
    check = tpp_prerequisite_status(live_tpp="off")

    assert check.status == "SKIPPED"
    assert check.details["mode"] == "off"
    assert "TPP_BASE_URL" in check.details["remediation"]
    assert "TPP_REPO_PATH" in check.details["remediation"]


def test_started_tpp_service_with_base_url_does_not_attempt_sibling_resolution(
    monkeypatch,
) -> None:
    def fail_resolver(_repo_path):  # pragma: no cover - defensive guard
        raise AssertionError(
            "_resolve_tpp_interpreter must not be invoked when TPP_BASE_URL is configured"
        )

    monkeypatch.setattr(verifier, "_resolve_tpp_interpreter", fail_resolver)

    def fail_popen(*_args, **_kwargs):  # pragma: no cover - defensive guard
        raise AssertionError("subprocess.Popen must not be invoked when TPP_BASE_URL is configured")

    monkeypatch.setattr(verifier.subprocess, "Popen", fail_popen)

    with verifier._started_tpp_service(
        {
            "TPP_BASE_URL": "https://tpp.example.test/",
            "TPP_ACCESS_TOKEN": "token",
            "TPP_OIDC_PROVIDER": "google",
        }
    ) as (base_url, process):
        assert base_url == "https://tpp.example.test"
        assert process is None


def test_tpp_interpreter_resolution_prefers_repo_venv(tmp_path) -> None:
    repo_path = tmp_path / "Travel-Plan-Permission"
    venv_python = repo_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/usr/bin/env python\n", encoding="utf-8")

    assert verifier._resolve_tpp_interpreter(repo_path) == [str(venv_python)]


def test_tpp_interpreter_resolution_uses_uv_lock_when_no_venv(monkeypatch, tmp_path) -> None:
    repo_path = tmp_path / "Travel-Plan-Permission"
    repo_path.mkdir()
    (repo_path / "uv.lock").write_text("", encoding="utf-8")
    monkeypatch.setattr(verifier.shutil, "which", lambda command: "/usr/local/bin/uv")

    assert verifier._resolve_tpp_interpreter(repo_path) == [
        "uv",
        "run",
        "--directory",
        str(repo_path),
        "python",
    ]


def test_tpp_interpreter_resolution_fails_with_actionable_message(monkeypatch, tmp_path) -> None:
    repo_path = tmp_path / "Travel-Plan-Permission"
    repo_path.mkdir()
    monkeypatch.setattr(verifier.shutil, "which", lambda command: None)

    try:
        verifier._resolve_tpp_interpreter(repo_path)
    except verifier.VerificationFailure as error:
        message = str(error)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("expected missing TPP interpreter to fail verification")

    assert "Cannot auto-start TPP" in message
    assert str(repo_path / ".venv" / "bin" / "python") in message
    assert "TPP_BASE_URL" in message


def test_started_tpp_service_captures_startup_stderr(monkeypatch, tmp_path) -> None:
    repo_path = tmp_path / "Travel-Plan-Permission"
    venv_python = repo_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/usr/bin/env python\n", encoding="utf-8")

    class FakeProcess:
        def __init__(self, *args, **kwargs):
            self.args = args[0]
            kwargs["stderr"].write(b"ModuleNotFoundError: No module named 'jinja2'\n")
            kwargs["stderr"].flush()

        def poll(self):
            return 1

        def terminate(self):  # pragma: no cover - should not terminate exited process
            raise AssertionError("process already exited")

    def fail_ready(_url: str) -> None:
        raise verifier.VerificationFailure("not ready")

    monkeypatch.setattr(verifier.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(verifier, "_wait_for_http", fail_ready)

    try:
        with verifier._started_tpp_service(
            {
                "TPP_REPO_PATH": str(repo_path),
                "TPP_ACCESS_TOKEN": "token",
                "TPP_OIDC_PROVIDER": "google",
            }
        ):
            raise AssertionError("service should not yield when readiness fails")
    except verifier.VerificationFailure as error:
        message = str(error)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("expected readiness failure")

    assert str(venv_python) in message
    assert "ModuleNotFoundError: No module named 'jinja2'" in message
    assert "stderr_tail" in message


def test_required_live_tpp_accepts_ready_prerequisite_after_success(monkeypatch) -> None:
    for name in (
        "TPP_BASE_URL",
        "TPP_ACCESS_TOKEN",
        "TPP_OIDC_PROVIDER",
        "TPP_REPO_PATH",
        "VITE_GOOGLE_MAPS_PROVIDER_STATE",
        "VITE_GOOGLE_MAPS_BROWSER_API_KEY",
        "VITE_GOOGLE_MAPS_EMBED_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TPP_BASE_URL", "https://tpp.example.test")
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "token")
    monkeypatch.setenv("TPP_OIDC_PROVIDER", "google")

    def fake_live_journey(
        _client, trip_id: str, _env: dict[str, str], **_: object
    ) -> dict[str, object]:
        return {
            "base_url": "https://tpp.example.test",
            "trip_id": trip_id,
            "proposal_id": f"proposal:{trip_id}",
            "execution_id": "exec-test",
            "status_poll": "succeeded",
            "evaluation_status": "non_compliant",
            "follow_up_status": "reoptimized",
            "native_transitions": {
                "policy_sync": f"POST /api/workspace/{trip_id}/policy/sync",
                "proposal_submit": f"POST /api/workspace/{trip_id}/proposal/submit",
                "proposal_refresh": f"POST /api/workspace/{trip_id}/proposal/refresh",
                "verdict_readback": f"GET /api/workspace/{trip_id}/proposal",
                "reoptimize": f"POST /api/workspace/{trip_id}/proposal/reoptimize",
            },
        }

    monkeypatch.setattr(verifier, "_run_live_tpp_journey", fake_live_journey)

    checks = run_product_journeys(live_tpp="required")
    by_name = {check.name: check for check in checks}

    assert by_name["live-tpp"].status == "PASS"
    assert by_name["live-tpp"].details["status_poll"] == "succeeded"


def test_frontend_runtime_smoke_reports_subprocess_success(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        assert args[0][-1] == "--smoke-only"
        assert kwargs["timeout"] == 180
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(verifier.subprocess, "run", fake_run)

    check = run_frontend_runtime_smoke()

    assert check == CheckResult(
        "frontend-runtime-smoke",
        "PASS",
        {
            "command": f"{verifier.REPO_ROOT / 'scripts' / 'check_full_stack_runtime.sh'} --smoke-only",
            "returncode": 0,
            "stdout_tail": "ok",
        },
    )


def test_frontend_runtime_smoke_reports_timeout_with_context(monkeypatch) -> None:
    def fake_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=args[0],
            timeout=kwargs["timeout"],
            output="stdout context",
            stderr="stderr context",
        )

    monkeypatch.setattr(verifier.subprocess, "run", fake_timeout)

    try:
        run_frontend_runtime_smoke()
    except verifier.VerificationFailure as error:
        message = str(error)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("expected smoke timeout to fail verification")

    assert "frontend/runtime smoke timed out" in message
    assert "stdout context" in message
    assert "stderr context" in message


def test_frontend_runtime_smoke_skips_when_prerequisites_are_missing(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="",
            stderr="Missing frontend test dependencies (`vitest` is unavailable under frontend/node_modules).",
        )

    monkeypatch.setattr(verifier.subprocess, "run", fake_run)

    check = run_frontend_runtime_smoke()

    assert check.status == "SKIPPED"
    assert check.details["reason"] == "runtime smoke prerequisites missing"


def test_main_succeeds_when_tpp_base_url_unset_in_auto_mode(monkeypatch) -> None:
    monkeypatch.delenv("TPP_BASE_URL", raising=False)
    monkeypatch.delenv("TPP_REPO_PATH", raising=False)
    monkeypatch.delenv("TPP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TPP_OIDC_PROVIDER", raising=False)

    monkeypatch.setattr(
        verifier,
        "run_frontend_runtime_smoke",
        lambda: CheckResult("frontend-runtime-smoke", "PASS", {"source": "stub"}),
    )
    monkeypatch.setattr(
        verifier,
        "run_product_journeys",
        lambda *, live_tpp: [CheckResult("live-tpp", "SKIPPED", {"mode": live_tpp})],
    )

    exit_code = verifier.main(["--live-tpp", "auto"])

    assert exit_code == 0


def _stub_frontend(monkeypatch) -> None:
    monkeypatch.setattr(
        verifier,
        "run_frontend_runtime_smoke",
        lambda: CheckResult("frontend-runtime-smoke", "PASS", {"source": "stub"}),
    )


def _passing_journeys(*, live_tpp: str) -> list[CheckResult]:
    return [
        CheckResult("local-leisure-journey", "PASS", {}),
        CheckResult("local-business-journey", "PASS", {}),
        CheckResult("map-provider", "SKIPPED", {"provider_state": "fallback"}),
        CheckResult("planner-llm", "SKIPPED", {"mode": "fallback"}),
        CheckResult("live-tpp", "PASS" if live_tpp == "required" else "SKIPPED", {}),
    ]


def test_main_writes_strict_pass_result_with_exact_command(monkeypatch, tmp_path) -> None:
    result_path = tmp_path / "evidence" / "result.json"
    monkeypatch.setenv(verifier.FULL_PRODUCT_RESULT_ENV, str(result_path))
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "ci-secret-token-value")
    _stub_frontend(monkeypatch)
    monkeypatch.setattr(verifier, "run_product_journeys", _passing_journeys)

    assert verifier.main(["--live-tpp=required"]) == 0

    result = json.loads(result_path.read_text())
    assert (
        result["command"] == "python scripts/check_full_product_verification.py --live-tpp=required"
    )
    assert result["status"] == "PASS"
    assert result["exit_code"] == 0
    assert result["required_skipped"] == 0
    assert [check["name"] for check in result["required_checks"]] == list(
        verifier.FULL_PRODUCT_REQUIRED_CHECKS
    )
    # Optional provider skips stay visible, outside the required checks.
    assert result["optional_observations"] == [
        {"name": "map-provider", "status": "SKIPPED"},
        {"name": "planner-llm", "status": "SKIPPED"},
    ]
    assert "ci-secret-token-value" not in result_path.read_text()


def test_main_records_skipped_required_live_tpp_as_not_pass(monkeypatch, tmp_path) -> None:
    result_path = tmp_path / "result.json"
    monkeypatch.setenv(verifier.FULL_PRODUCT_RESULT_ENV, str(result_path))
    _stub_frontend(monkeypatch)
    monkeypatch.setattr(verifier, "run_product_journeys", _passing_journeys)

    # Disabled live-TPP keeps the existing zero exit but cannot produce a PASS result.
    assert verifier.main(["--live-tpp=off"]) == 0

    result = json.loads(result_path.read_text())
    assert result["command"] == "python scripts/check_full_product_verification.py --live-tpp=off"
    assert result["status"] == "SKIPPED"
    assert result["required_skipped"] == 1


def test_required_live_tpp_blocked_exits_nonzero_and_records_failure(monkeypatch, tmp_path) -> None:
    for name in (
        "TPP_BASE_URL",
        "TPP_ACCESS_TOKEN",
        "TPP_OIDC_PROVIDER",
        "TPP_REPO_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TPP_REPO_PATH", str(tmp_path / "missing-tpp"))
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "ci-secret-token-value")
    result_path = tmp_path / "result.json"
    monkeypatch.setenv(verifier.FULL_PRODUCT_RESULT_ENV, str(result_path))
    _stub_frontend(monkeypatch)

    assert verifier.main(["--live-tpp=required"]) == 1

    result = json.loads(result_path.read_text())
    assert result["status"] == "FAIL"
    assert result["exit_code"] == 1
    assert result["failure"].startswith("VerificationFailure: ")
    assert {"name": "live-tpp", "status": "MISSING"} in result["required_checks"]
    assert "ci-secret-token-value" not in result_path.read_text()


def test_contract_report_mode_does_not_write_strict_result(monkeypatch, tmp_path) -> None:
    result_path = tmp_path / "result.json"
    monkeypatch.setenv(verifier.FULL_PRODUCT_RESULT_ENV, str(result_path))
    monkeypatch.setattr(verifier, "run_product_journeys", _passing_journeys)
    monkeypatch.setattr(verifier, "run_contract_report", list)

    assert verifier.main(["--live-tpp=required", f"--contract-report={tmp_path / 'r.json'}"]) == 0
    assert not result_path.exists()


def _install_live_tpp_transport_stub(monkeypatch) -> list[tuple[str, str]]:
    from trip_planner.integrations.tpp import client as tpp_client_module

    calls: list[tuple[str, str]] = []
    outcomes_by_execution: dict[str, str] = {}

    def fake_send_json_request(
        self,
        *,
        method: str,
        path: str,
        url: str,
        json_payload: dict[str, Any],
    ) -> dict[str, object]:
        del self, url
        calls.append((method, path))
        if method == "GET" and path == "/api/planner/policy-snapshot":
            req = dict(json_payload.get("request") or {})
            return {
                "trip_id": req.get("trip_id", "trip-unknown"),
                "freshness": "current",
                "generated_at": "2026-11-27T00:00:00Z",
                "expires_at": "2026-11-28T00:00:00Z",
                "invalidated_at": None,
                "invalidation_reason": None,
                "policy_status": "pass",
                "booking_requirements": [
                    {"code": "approved_channel", "summary": "Book through an approved channel."}
                ],
                "documentation_rules": [
                    {"code": "fare_evidence", "summary": "Attach lowest fare evidence."}
                ],
                "approval_triggers": [
                    {"code": "manager_review", "summary": "Manager approval required."}
                ],
                "airfare_rules": {"max_cabin": "economy", "max_over_lowest_fare_usd": 100},
                "lodging_rules": {"max_nightly_rate_usd": 325},
                "ground_transport_rules": {},
                "meal_rules": {},
                "budget_rules": {},
                "comparable_requirements": {"lodging": 1},
                "versioning": {
                    "contract_version": "2026-04-11",
                    "policy_version": "2026.11",
                    "planner_known_policy_version": None,
                    "compatible_with_planner_cache": True,
                    "etag": "policy-live-2071",
                },
            }
        if method == "POST" and path == "/api/planner/proposals":
            req = dict(json_payload.get("request") or {})
            trip_plan = dict(json_payload.get("trip_plan") or {})
            trip_id = str(req.get("trip_id") or trip_plan.get("trip_id") or "trip-unknown")
            proposal_id = str(req.get("proposal_id") or f"proposal:{trip_id}")
            selected_fare = float(trip_plan.get("selected_fare") or 0.0)
            lowest_fare = float(trip_plan.get("lowest_fare") or selected_fare)
            execution_id = f"exec-live-2071-{len(outcomes_by_execution) + 1}"
            is_compliant = selected_fare <= lowest_fare
            outcomes_by_execution[execution_id] = "compliant" if is_compliant else "non_compliant"
            if is_compliant:
                return {
                    "operation": "submit_proposal",
                    "submission_status": "submitted",
                    "request_id": "tpp-submit-2071",
                    "correlation_id": {
                        "value": f"submit-proposal:{trip_id}",
                        "issued_by": "tpp",
                    },
                    "transport_pattern": "deferred",
                    "execution_status": {
                        "state": "deferred",
                        "terminal": False,
                        "summary": "Proposal queued for evaluation",
                        "poll_after_seconds": 0,
                        "external_status": "202 Accepted",
                        "updated_at": "2026-11-27T00:00:01Z",
                    },
                    "result_payload": {
                        "execution_id": execution_id,
                        "queue_state": "waiting_for_policy_engine",
                        "trip_id": trip_id,
                        "proposal_id": proposal_id,
                    },
                    "received_at": "2026-11-27T00:00:01Z",
                    "status_endpoint": (
                        f"https://tpp.example.test/api/planner/proposals/{proposal_id}"
                        f"/executions/{execution_id}"
                    ),
                }
            return {
                "operation": "submit_proposal",
                "submission_status": "rejected",
                "request_id": "tpp-submit-2071",
                "correlation_id": {
                    "value": f"submit-proposal:{trip_id}",
                    "issued_by": "tpp",
                },
                "transport_pattern": "sync",
                "execution_status": {
                    "state": "failed",
                    "terminal": True,
                    "summary": "Proposal blocked by policy",
                    "external_status": "200 OK",
                    "updated_at": "2026-11-27T00:00:01Z",
                },
                "result_payload": {
                    "execution_id": execution_id,
                    "queue_state": "blocked_by_policy",
                    "trip_id": trip_id,
                    "proposal_id": proposal_id,
                    "blocking_codes": ["fare_above_lowest"],
                },
                "error": {
                    "code": "proposal_blocked_by_policy",
                    "message": "Selected fare exceeds lowest available fare.",
                    "category": "policy",
                    "retryable": False,
                },
                "received_at": "2026-11-27T00:00:01Z",
                "status_endpoint": (
                    f"https://tpp.example.test/api/planner/proposals/{proposal_id}"
                    f"/executions/{execution_id}"
                ),
            }
        if method == "GET" and "/executions/" in path and not path.endswith("/evaluation-result"):
            execution_id = path.rsplit("/", 1)[-1]
            proposal_id = str(json_payload.get("proposal_id") or "proposal-unknown")
            outcome = outcomes_by_execution.get(execution_id, "compliant")
            if outcome == "compliant":
                return {
                    "operation": "poll_execution_status",
                    "transport_pattern": "deferred",
                    "execution_status": {
                        "state": "deferred",
                        "terminal": False,
                        "summary": "Awaiting evaluator completion",
                        "updated_at": "2026-11-27T00:00:02Z",
                    },
                    "result_payload": {
                        "execution_id": execution_id,
                        "proposal_id": proposal_id,
                        "queue_state": "waiting_for_policy_engine",
                    },
                    "received_at": "2026-11-27T00:00:02Z",
                    "status_endpoint": (
                        f"https://tpp.example.test/api/planner/proposals/{proposal_id}"
                        f"/executions/{execution_id}"
                    ),
                }
            return {
                "operation": "poll_execution_status",
                "transport_pattern": "sync",
                "execution_status": {
                    "state": "failed",
                    "terminal": True,
                    "summary": "Proposal blocked by policy",
                    "updated_at": "2026-11-27T00:00:02Z",
                },
                "result_payload": {
                    "execution_id": execution_id,
                    "proposal_id": proposal_id,
                    "queue_state": "blocked_by_policy",
                    "blocking_codes": ["fare_above_lowest"],
                },
                "error": {
                    "code": "proposal_blocked_by_policy",
                    "message": "Selected fare exceeds lowest available fare.",
                    "category": "policy",
                    "retryable": False,
                },
                "received_at": "2026-11-27T00:00:02Z",
                "status_endpoint": (
                    f"https://tpp.example.test/api/planner/proposals/{proposal_id}"
                    f"/executions/{execution_id}"
                ),
            }
        if method == "GET" and path.endswith("/evaluation-result"):
            execution_id = path.split("/executions/", 1)[1].split("/", 1)[0]
            trip_id = str(json_payload.get("trip_id") or "trip-unknown")
            proposal_id = str(json_payload.get("proposal_id") or f"proposal:{trip_id}")
            proposal_version = str(json_payload.get("proposal_version") or "v1")
            outcome = outcomes_by_execution.get(execution_id, "non_compliant")
            return {
                "trip_id": trip_id,
                "proposal_id": proposal_id,
                "proposal_version": proposal_version,
                "execution_id": execution_id,
                "request_id": f"eval-2071-{execution_id}",
                "correlation_id": {
                    "value": f"submit-proposal:{trip_id}",
                    "issued_by": "tpp",
                },
                "outcome": outcome,
                "result_endpoint": f"GET /api/planner/executions/{execution_id}/evaluation-result",
                "status_endpoint": (
                    f"https://tpp.example.test/api/planner/proposals/{proposal_id}"
                    f"/executions/{execution_id}"
                ),
                "policy_result": {
                    "status": "fail" if outcome == "non_compliant" else "pass",
                    "issues": [],
                    "policy_version": "2026.11",
                },
                "blocking_issues": (
                    [
                        {
                            "code": "fare_above_lowest",
                            "summary": "Selected fare exceeds lowest available fare threshold.",
                            "category": "airfare",
                        }
                    ]
                    if outcome == "non_compliant"
                    else []
                ),
                "preferred_alternatives": (
                    [
                        {
                            "category": "airfare",
                            "summary": "Rebook the lowest available economy fare.",
                            "rationale": "Matches the $400 lowest fare threshold.",
                        }
                    ]
                    if outcome == "non_compliant"
                    else []
                ),
                "exception_requirements": [],
                "reoptimization_guidance": [],
                "generated_at": "2026-11-27T00:00:03Z",
            }
        raise AssertionError(f"Unexpected TPP transport request: {method} {path}")

    monkeypatch.setattr(
        tpp_client_module.HTTPTPPIntegrationClient,
        "_send_json_request",
        fake_send_json_request,
    )
    return calls


def test_live_tpp_journey_reoptimizes_non_compliant_verdict_and_persists_plan(
    monkeypatch, tmp_path
) -> None:
    _install_live_tpp_transport_stub(monkeypatch)
    env = {
        "TPP_BASE_URL": "https://tpp.example.test",
        "TPP_ACCESS_TOKEN": "token-2071",
        "TPP_OIDC_PROVIDER": "google",
        "TPP_ORGANIZATION_ID": "org-2071",
    }
    with (
        verifier._temporary_database_url(f"sqlite:///{tmp_path / 'reoptimize.db'}"),
        verifier._force_planner_fallback_runtime(),
    ):
        verifier.reset_database_state()
        verifier.ensure_database_ready()
        with verifier.TestClient(verifier.create_app()) as client:
            verifier._signup(client)
            trip_id = verifier._create_trip(
                client,
                mode="business",
                title="Live reoptimize journey",
                region="Chicago",
            )
            live_details = verifier._run_live_tpp_journey(
                client,
                trip_id,
                env,
                expected_evaluation_status="non_compliant",
            )

            assert live_details["evaluation_status"] == "non_compliant"
            assert live_details["follow_up_status"] == "reoptimized"
            assert live_details["verdict_readback"]["status"] == "non_compliant"
            assert live_details["verdict_readback"]["follow_up_status"] == "reoptimization_required"
            assert live_details["native_transitions"]["reoptimize"] == (
                f"POST /api/workspace/{trip_id}/proposal/reoptimize"
            )
            assert live_details["reoptimization_readback"]["follow_up_status"] == "reoptimized"
            assert (
                live_details["reoptimization_readback"]["source_version_id"]
                == live_details["source_version_id"]
            )

            persisted_proposal = client.get(f"/api/workspace/{trip_id}/proposal")
            assert persisted_proposal.status_code == 200
            proposal_state = persisted_proposal.json()["proposal_state"]
            assert proposal_state["evaluation"]["evaluation_result"]["status"] == "non_compliant"
            assert proposal_state["follow_up"]["status"] == "reoptimized"
            plan = proposal_state["follow_up"]["reoptimization_plan"]
            assert plan["target_title"]
            assert plan["source_version"]["version_id"] == live_details["source_version_id"]

            reloaded_workspace = client.get(f"/api/workspace/{trip_id}")
            assert reloaded_workspace.status_code == 200
            reloaded_state = reloaded_workspace.json()["proposal_state"]
            assert reloaded_state["summary"]["evaluation_result_status"] == "non_compliant"
            reloaded_plan = reloaded_state["follow_up"]["reoptimization_plan"]
            assert reloaded_plan["target_title"] == plan["target_title"]
            assert reloaded_plan["reaction_kind"] == plan["reaction_kind"]
            assert reloaded_plan["candidate_categories"] == plan["candidate_categories"]
            assert (
                reloaded_plan["source_version"]["version_id"] == live_details["source_version_id"]
            )


def test_live_tpp_journey_leaves_compliant_control_unreoptimized(monkeypatch, tmp_path) -> None:
    _install_live_tpp_transport_stub(monkeypatch)
    env = {
        "TPP_BASE_URL": "https://tpp.example.test",
        "TPP_ACCESS_TOKEN": "token-2071",
        "TPP_OIDC_PROVIDER": "google",
        "TPP_ORGANIZATION_ID": "org-2071",
    }
    with (
        verifier._temporary_database_url(f"sqlite:///{tmp_path / 'compliant.db'}"),
        verifier._force_planner_fallback_runtime(),
    ):
        verifier.reset_database_state()
        verifier.ensure_database_ready()
        with verifier.TestClient(verifier.create_app()) as client:
            verifier._signup(client)
            trip_id = verifier._create_trip(
                client,
                mode="business",
                title="Compliant control journey",
                region="Chicago",
            )
            live_details = verifier._run_live_tpp_journey(
                client,
                trip_id,
                env,
                expected_evaluation_status="compliant",
            )

            assert live_details["evaluation_status"] == "compliant"
            assert live_details["follow_up_status"] == "resolved"
            assert "reoptimize" not in live_details["native_transitions"]
            assert "reoptimization_readback" not in live_details

            persisted = client.get(f"/api/workspace/{trip_id}/proposal").json()["proposal_state"]
            assert persisted["follow_up"]["status"] == "resolved"
            assert "reoptimization_plan" not in persisted["follow_up"]


def test_live_tpp_journey_fails_when_reoptimization_fails_or_readback_mismatches(
    monkeypatch, tmp_path
) -> None:
    _install_live_tpp_transport_stub(monkeypatch)
    env = {
        "TPP_BASE_URL": "https://tpp.example.test",
        "TPP_ACCESS_TOKEN": "token-2071",
        "TPP_OIDC_PROVIDER": "google",
        "TPP_ORGANIZATION_ID": "org-2071",
    }
    with (
        verifier._temporary_database_url(f"sqlite:///{tmp_path / 'reoptimize-fail.db'}"),
        verifier._force_planner_fallback_runtime(),
    ):
        verifier.reset_database_state()
        verifier.ensure_database_ready()
        with verifier.TestClient(verifier.create_app()) as client:
            verifier._signup(client)
            trip_id = verifier._create_trip(
                client,
                mode="business",
                title="Broken reoptimize journey",
                region="Chicago",
            )
            original_post = client.post

            def failing_reoptimize_post(url: str, *args, **kwargs):
                if str(url).endswith("/proposal/reoptimize"):
                    return verifier.TestClient(verifier.create_app()).get("/api/no-such-route")
                return original_post(url, *args, **kwargs)

            monkeypatch.setattr(client, "post", failing_reoptimize_post)
            try:
                verifier._run_live_tpp_journey(
                    client,
                    trip_id,
                    env,
                    expected_evaluation_status="non_compliant",
                )
            except verifier.VerificationFailure as error:
                assert "live TPP proposal reoptimization failed" in str(error)
            else:  # pragma: no cover - assertion guard
                raise AssertionError("expected HTTP failure on /proposal/reoptimize to fail")

            monkeypatch.setattr(client, "post", original_post)
            try:
                verifier._assert_native_live_tpp_reoptimization_readback(
                    trip_id=trip_id,
                    evaluation_id="eval-1",
                    expected_source_version={"version_id": "ver-expected", "trip_id": trip_id},
                    expected_evaluation_status="non_compliant",
                    reoptimized_state={
                        "evaluation": {
                            "evaluation_result": {
                                "evaluation_id": "eval-1",
                                "status": "non_compliant",
                            }
                        },
                        "follow_up": {
                            "status": "reoptimized",
                            "reoptimization_plan": {
                                "target_title": "Plan",
                                "reaction_kind": "narrow_candidates",
                                "source_version": {"version_id": "ver-wrong", "trip_id": trip_id},
                            },
                        },
                    },
                    reoptimized_summary={
                        "evaluation_result_status": "non_compliant",
                        "follow_up_status": "reoptimized",
                    },
                )
            except verifier.VerificationFailure as error:
                assert "did not retain plan and source lineage" in str(error)
            else:  # pragma: no cover - assertion guard
                raise AssertionError("expected mismatched source_version_id to fail")
