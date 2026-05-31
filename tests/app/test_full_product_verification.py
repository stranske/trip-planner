import os
import subprocess

from scripts import check_full_product_verification as verifier
from scripts.check_full_product_verification import (
    CheckResult,
    classify_map_prerequisite,
    classify_planner_llm_prerequisite,
    run_product_journeys,
    run_frontend_runtime_smoke,
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
    assert by_name["local-business-journey"].details["evaluation_status"] == "compliant"
    assert by_name["local-business-journey"].details["follow_up_status"] == "resolved"
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

    def fake_live_journey(_client, trip_id: str, _env: dict[str, str]) -> dict[str, str]:
        return {
            "base_url": "https://tpp.example.test",
            "trip_id": trip_id,
            "proposal_id": f"proposal:{trip_id}",
            "execution_id": "exec-test",
            "status_poll": "succeeded",
            "evaluation_status": "compliant",
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
