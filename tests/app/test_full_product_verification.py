import os
import subprocess

from scripts import check_full_product_verification as verifier
from scripts.check_full_product_verification import (
    CheckResult,
    classify_map_prerequisite,
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


def test_live_tpp_auto_reports_missing_config_as_skipped(monkeypatch, tmp_path) -> None:
    for name in (
        "TPP_BASE_URL",
        "TPP_ACCESS_TOKEN",
        "TPP_OIDC_PROVIDER",
        "TPP_REPO_PATH",
    ):
        monkeypatch.delenv(name, raising=False)

    check = tpp_prerequisite_status(live_tpp="auto", default_repo_path=tmp_path / "missing")

    assert check == CheckResult(
        "live-tpp",
        "SKIPPED",
        {
            "missing_env": "TPP_BASE_URL or TPP_REPO_PATH",
            "default_repo_path": str(tmp_path / "missing"),
        },
    )


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

    assert check == CheckResult(
        "live-tpp",
        "SKIPPED",
        {
            "missing_env": "TPP_BASE_URL or TPP_REPO_PATH",
            "default_repo_path": str(tmp_path / "missing"),
        },
    )


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
