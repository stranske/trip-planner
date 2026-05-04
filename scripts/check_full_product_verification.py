#!/usr/bin/env python3
"""Full-product verification gate for local and preview-oriented checks."""

from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator, Mapping
from typing import Any
from urllib import request as urllib_request

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from trip_planner.app.main import create_app  # noqa: E402
from trip_planner.persistence.db import ensure_database_ready, reset_database_state  # noqa: E402

DEFAULT_TPP_REPO_PATH = REPO_ROOT.parent / "Travel-Plan-Permission"
TPP_PORT = 8765


class VerificationFailure(AssertionError):
    """Raised when a product journey does not satisfy the verification contract."""

    def __init__(self, message: str, **details: Any) -> None:
        suffix = f" ({json.dumps(details, sort_keys=True)})" if details else ""
        super().__init__(f"{message}{suffix}")


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    details: dict[str, Any]


def _require(condition: bool, message: str, **details: Any) -> None:
    if not condition:
        raise VerificationFailure(message, **details)


def _fixture(*parts: str) -> dict[str, Any]:
    path = REPO_ROOT / "tests" / "fixtures" / "integrations" / "tpp" / Path(*parts)
    return json.loads(path.read_text(encoding="utf-8"))


def run_frontend_runtime_smoke() -> CheckResult:
    command = [str(REPO_ROOT / "scripts" / "check_full_stack_runtime.sh"), "--smoke-only"]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired as exc:
        details: dict[str, Any] = {
            "command": " ".join(command),
            "timeout": exc.timeout,
        }
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        if stdout.strip():
            details["stdout_tail"] = stdout.strip()[-1200:]
        if stderr.strip():
            details["stderr_tail"] = stderr.strip()[-1200:]
        raise VerificationFailure("frontend/runtime smoke timed out", **details) from exc
    details = {
        "command": " ".join(command),
        "returncode": completed.returncode,
    }
    if completed.stdout.strip():
        details["stdout_tail"] = completed.stdout.strip()[-1200:]
    if completed.stderr.strip():
        details["stderr_tail"] = completed.stderr.strip()[-1200:]
    if completed.returncode != 0:
        stderr = completed.stderr
        if (
            "Missing frontend test dependencies" in stderr
            or "Missing backend test dependencies" in stderr
        ):
            details["reason"] = "runtime smoke prerequisites missing"
            return CheckResult("frontend-runtime-smoke", "SKIPPED", details)
        raise VerificationFailure("frontend/runtime smoke failed", **details)
    return CheckResult("frontend-runtime-smoke", "PASS", details)


def _signup(client: TestClient) -> str:
    response = client.post(
        "/api/auth/signup",
        json={
            "email": f"full-product-{time.time_ns()}@example.com",
            "password": "password123",
            "display_name": "Full Product Verifier",
        },
    )
    _require(response.status_code == 201, "signup failed", status=response.status_code)
    return response.json()["user"]["user_id"]


def _create_trip(client: TestClient, *, mode: str, title: str, region: str) -> str:
    start_date = date.today() + timedelta(days=45)
    end_date = start_date + timedelta(days=2)
    response = client.post(
        "/api/trips",
        json={
            "title": title,
            "summary": f"Full-product verification for {title}.",
            "mode": mode,
            "trip_frame": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "duration_days": 3,
                "primary_regions": [region],
                "traveler_party": {
                    "kind": "team" if mode == "business" else "solo",
                    "traveler_count": 3 if mode == "business" else 1,
                    "notes": "Created by full-product verification.",
                },
            },
        },
    )
    _require(response.status_code == 201, "trip creation failed", status=response.status_code)
    return response.json()["trip"]["trip_id"]


def _proposal_payload(trip_id: str) -> dict[str, Any]:
    return {
        "proposal_id": f"proposal:{trip_id}",
        "trip_id": trip_id,
        "mode": "business",
        "traveler_context": {
            "employee_type": "employee",
            "traveler_experience": "frequent",
            "home_airport": "ORD",
            "loyalty_programs": ["United"],
            "mobility_or_access_needs": [],
        },
        "selected_options": [
            {
                "category": "airfare",
                "option_id": "flight-1",
                "label": "United 123",
                "vendor": "United",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 620.0,
                    "min_amount": 620.0,
                    "max_amount": 620.0,
                },
                "justification_refs": ["fare-policy"],
            }
        ],
        "cost_summary": {
            "currency": "USD",
            "total_estimated_cost": 620.0,
            "category_estimates": {"airfare": 620.0},
            "notes": ["Costs include taxes."],
        },
        "comparables": [
            {
                "category": "airfare",
                "label": "Flexible fare",
                "vendor": "United",
                "booking_channel": "Concur",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 710.0,
                    "min_amount": 710.0,
                    "max_amount": 710.0,
                },
                "notes": ["Refundable alternative."],
            }
        ],
        "approval_notes": ["Manager review required before booking."],
        "constraint_set_id": "policy-standard-2026-02",
    }


def _prepared_policy_request(trip_id: str) -> dict[str, Any]:
    request_payload = copy.deepcopy(_fixture("policy", "standard_policy_sync.json")["request"])
    request_payload["trip_id"] = trip_id
    return request_payload


def _prepared_submission_request(trip_id: str, proposal_id: str) -> dict[str, Any]:
    request_payload = copy.deepcopy(_fixture("proposal_submit_deferred.json")["request"])
    request_payload["trip_id"] = trip_id
    request_payload["proposal_id"] = proposal_id
    request_payload["payload"]["proposal_ref"] = proposal_id
    return request_payload


def _prepared_evaluation_request(
    trip_id: str, proposal_id: str, execution_id: str
) -> dict[str, Any]:
    request_payload = copy.deepcopy(_fixture("results", "approved_evaluation.json")["request"])
    request_payload["trip_id"] = trip_id
    request_payload["proposal_id"] = proposal_id
    request_payload["payload"]["execution_id"] = execution_id
    return request_payload


def _prepared_evaluation_response(
    trip_id: str,
    proposal_id: str,
    execution_id: str,
) -> dict[str, Any]:
    response_payload = copy.deepcopy(_fixture("results", "approved_evaluation.json")["response"])
    result_payload = response_payload["result_payload"]
    result_payload["execution_id"] = execution_id
    result_payload["trip_id"] = trip_id
    result_payload["proposal_id"] = proposal_id
    result_payload["evaluation_result"]["proposal_id"] = proposal_id
    return response_payload


def _assert_workspace_scenario_context(payload: dict[str, Any], *, trip_id: str) -> None:
    scenario_search = payload["scenario_search"]
    runtime_comparison = payload["runtime_scenario_comparison"]
    scenarios = list(scenario_search.get("scenarios") or [])
    comparison_rows = list(runtime_comparison.get("scenarios") or [])
    _require(bool(scenarios), "workspace scenario search returned no scenarios", trip_id=trip_id)
    _require(
        bool(comparison_rows),
        "workspace comparison returned no scenarios",
        trip_id=trip_id,
    )
    for scenario in scenarios:
        route_sequence = scenario["scenario_summary"].get("route_sequence") or []
        _require(
            len(route_sequence) >= 2,
            "workspace scenario is missing timeline route context",
            trip_id=trip_id,
            scenario_id=scenario.get("scenario_id"),
        )
    for row in comparison_rows:
        _require(
            row.get("route_sequence"),
            "workspace comparison row is missing map route context",
            trip_id=trip_id,
            scenario_id=row.get("scenario_id"),
        )


def _assert_runtime_inventory(payload: dict[str, Any], *, trip_id: str) -> None:
    inventory_summary = payload["inventory_summary"]
    _require(
        inventory_summary["runtime_state"]["status"] == "ready",
        "inventory runtime was not ready",
        trip_id=trip_id,
    )
    _require(
        inventory_summary["bundle_count"] > 0,
        "journey produced no source-backed inventory bundles",
        trip_id=trip_id,
    )
    source_metadata = inventory_summary["source_metadata"]
    _require(
        source_metadata["origin"] == "runtime",
        "workspace did not expose runtime source metadata",
        trip_id=trip_id,
        source_metadata=source_metadata,
    )
    fixture_names = source_metadata.get("fixture_names") or []
    _require(
        not fixture_names,
        "persisted workspace unexpectedly exposed fixture-backed runtime labels",
        trip_id=trip_id,
        fixture_names=fixture_names,
    )


def _assert_planner_runtime_response(payload: dict[str, Any], *, trip_id: str) -> str:
    runtime = dict(payload.get("runtime") or {})
    _require(
        runtime.get("mode") in {"fallback", "model"},
        "planner turn did not report a runtime mode",
        trip_id=trip_id,
        runtime=runtime,
    )
    _require(
        payload.get("conversation_id") == f"planner-conversation:{trip_id}",
        "planner turn did not use the trip-scoped runtime conversation",
        trip_id=trip_id,
        conversation_id=payload.get("conversation_id"),
    )
    _require(
        bool(payload.get("available_tools")),
        "planner turn did not expose model-tool runtime capabilities",
        trip_id=trip_id,
    )
    return str(runtime["mode"])


def classify_map_prerequisite(env: Mapping[str, str] | None = None) -> CheckResult:
    env_map = os.environ if env is None else env
    api_key = (
        env_map.get("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "").strip()
        or env_map.get("VITE_GOOGLE_MAPS_EMBED_API_KEY", "").strip()
    )
    provider_state = env_map.get("VITE_GOOGLE_MAPS_PROVIDER_STATE", "ready").strip() or "ready"
    if not api_key:
        return CheckResult(
            "map-provider",
            "SKIPPED",
            {
                "provider_state": "fallback",
                "missing_env": "VITE_GOOGLE_MAPS_BROWSER_API_KEY",
                "message": "Fallback map path is expected without live Google Maps credentials.",
            },
        )
    if provider_state == "ready":
        return CheckResult(
            "map-provider",
            "PASS",
            {"provider_state": "provider-backed", "env": "VITE_GOOGLE_MAPS_*"},
        )
    if provider_state == "loading":
        return CheckResult(
            "map-provider",
            "BLOCKED",
            {"provider_state": "loading", "message": "Provider adapter has not become ready."},
        )
    return CheckResult(
        "map-provider",
        "FAIL",
        {"provider_state": provider_state, "message": "Configured map provider reported an error."},
    )


def tpp_prerequisite_status(
    *,
    live_tpp: str,
    env: Mapping[str, str] | None = None,
    default_repo_path: Path = DEFAULT_TPP_REPO_PATH,
) -> CheckResult:
    env_map = os.environ if env is None else env
    configured = {
        "TPP_BASE_URL": env_map.get("TPP_BASE_URL", "").strip(),
        "TPP_ACCESS_TOKEN": env_map.get("TPP_ACCESS_TOKEN", "").strip(),
        "TPP_OIDC_PROVIDER": env_map.get("TPP_OIDC_PROVIDER", "").strip(),
        "TPP_REPO_PATH": env_map.get("TPP_REPO_PATH", "").strip(),
    }
    has_transport_target = bool(configured["TPP_BASE_URL"] or configured["TPP_REPO_PATH"])
    explicit = any(configured.values())
    if live_tpp == "off":
        return CheckResult("live-tpp", "SKIPPED", {"mode": "off"})
    if live_tpp == "auto" and not explicit:
        return CheckResult(
            "live-tpp",
            "SKIPPED",
            {
                "missing_env": "TPP_BASE_URL or TPP_REPO_PATH",
                "default_repo_path": str(default_repo_path),
            },
        )
    if live_tpp == "auto" and not has_transport_target:
        return CheckResult(
            "live-tpp",
            "SKIPPED",
            {
                "missing_env": "TPP_BASE_URL or TPP_REPO_PATH",
                "default_repo_path": str(default_repo_path),
            },
        )
    missing = [name for name in ("TPP_ACCESS_TOKEN", "TPP_OIDC_PROVIDER") if not configured[name]]
    invalid_path: dict[str, str] = {}
    if not configured["TPP_BASE_URL"] and not configured["TPP_REPO_PATH"]:
        if live_tpp == "required" and default_repo_path.is_dir():
            configured["TPP_REPO_PATH"] = str(default_repo_path)
        else:
            missing.append("TPP_BASE_URL or TPP_REPO_PATH")
    if configured["TPP_REPO_PATH"]:
        repo_path = Path(configured["TPP_REPO_PATH"])
        if not repo_path.exists() or not repo_path.is_dir():
            invalid_path["TPP_REPO_PATH"] = configured["TPP_REPO_PATH"]
    if missing or invalid_path:
        details: dict[str, Any] = {}
        if missing:
            details["missing_env"] = sorted(set(missing))
        if invalid_path:
            details["invalid_path"] = invalid_path
        return CheckResult("live-tpp", "BLOCKED", details)
    return CheckResult("live-tpp", "READY", configured)


def _wait_for_http(url: str, *, timeout_seconds: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    last_status: int | None = None
    while time.monotonic() < deadline:
        try:
            with urllib_request.urlopen(url, timeout=1) as response:
                last_status = response.status
                if 200 <= response.status < 400:
                    return
        except Exception as exc:  # pragma: no cover - exercised by integration use
            last_error = exc
            status_code = getattr(exc, "code", None)
            if isinstance(status_code, int):
                last_status = status_code
        time.sleep(0.25)
    details: list[str] = []
    if last_status is not None:
        details.append(f"last_status={last_status}")
    if last_error is not None:
        details.append(f"last_error={last_error}")
    suffix = f" ({', '.join(details)})" if details else ""
    raise VerificationFailure(f"TPP service did not become ready at {url}{suffix}")


def _free_local_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", preferred))
        except OSError:
            sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _resolve_tpp_interpreter(repo_path: Path) -> list[str]:
    venv_python = repo_path / ".venv" / "bin" / "python"
    if venv_python.exists():
        return [str(venv_python)]
    if (repo_path / "uv.lock").exists() and shutil.which("uv"):
        return ["uv", "run", "--directory", str(repo_path), "python"]
    raise VerificationFailure(
        "Cannot auto-start TPP: no usable TPP Python environment",
        venv_python=str(venv_python),
        uv_lock=str(repo_path / "uv.lock"),
        remediation=(
            f"Install TPP dependencies into {repo_path}/.venv, install uv for the repo's "
            "uv.lock path, or set TPP_BASE_URL to skip auto-start."
        ),
    )


def _tail_file(path: Path, *, line_count: int = 50) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-line_count:])


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
            process.kill()
            process.wait(timeout=5)


@contextmanager
def _started_tpp_service(
    env: dict[str, str],
) -> Iterator[tuple[str, subprocess.Popen[bytes] | None]]:
    base_url = env.get("TPP_BASE_URL", "").strip()
    repo_path = env.get("TPP_REPO_PATH", "").strip()
    if base_url:
        yield base_url.rstrip("/"), None
        return

    port = _free_local_port(TPP_PORT)
    base_url = f"http://127.0.0.1:{port}"
    repo_root = Path(repo_path)
    interpreter = _resolve_tpp_interpreter(repo_root)
    service_env = {
        **os.environ,
        "PYTHONPATH": str(repo_root / "src"),
        "TPP_BASE_URL": base_url,
        "TPP_AUTH_MODE": "static-token",
        "TPP_ACCESS_TOKEN": env["TPP_ACCESS_TOKEN"],
        "TPP_OIDC_PROVIDER": env["TPP_OIDC_PROVIDER"],
    }
    stdout_file = tempfile.NamedTemporaryFile(prefix="tpp-service-", suffix=".stdout", delete=False)
    stderr_file = tempfile.NamedTemporaryFile(prefix="tpp-service-", suffix=".stderr", delete=False)
    stdout_path = Path(stdout_file.name)
    stderr_path = Path(stderr_file.name)
    command = [
        *interpreter,
        "-m",
        "travel_plan_permission.http_service",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    process = subprocess.Popen(
        command,
        cwd=repo_root,
        env=service_env,
        stdout=stdout_file,
        stderr=stderr_file,
    )
    stdout_file.close()
    stderr_file.close()
    try:
        try:
            _wait_for_http(f"{base_url}/readyz")
        except VerificationFailure as exc:
            _stop_process(process)
            raise VerificationFailure(
                "TPP service did not become ready",
                ready_url=f"{base_url}/readyz",
                interpreter=" ".join(interpreter),
                command=" ".join(command),
                cwd=str(repo_root),
                returncode=process.poll(),
                stdout_tail=_tail_file(stdout_path),
                stderr_tail=_tail_file(stderr_path),
            ) from exc
        yield base_url, process
    finally:
        _stop_process(process)
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)


def _run_live_tpp_journey(client: TestClient, trip_id: str, env: dict[str, str]) -> dict[str, Any]:
    with _started_tpp_service(env) as (base_url, _process):
        tpp_env = {
            "TPP_BASE_URL": base_url,
            "TPP_ACCESS_TOKEN": env["TPP_ACCESS_TOKEN"],
            "TPP_OIDC_PROVIDER": env["TPP_OIDC_PROVIDER"],
        }
        previous = {key: os.environ.get(key) for key in tpp_env}
        os.environ.update(tpp_env)
        try:
            policy_request = _prepared_policy_request(trip_id)
            policy_response = client.put(
                f"/api/workspace/{trip_id}/policy",
                json={"request": policy_request, "response": None, "tags": ["full-product-live"]},
            )
            _require(
                policy_response.status_code == 200,
                "live TPP policy sync failed",
                status=policy_response.status_code,
                body=policy_response.text,
                trip_id=trip_id,
            )

            proposal = _proposal_payload(trip_id)
            submission_request = _prepared_submission_request(trip_id, proposal["proposal_id"])
            submission_response = client.put(
                f"/api/workspace/{trip_id}/proposal",
                json={
                    "proposal": proposal,
                    "request": submission_request,
                    "response": None,
                    "proposal_version": "proposal-v3",
                    "scenario_id": "scenario-a",
                },
            )
            _require(
                submission_response.status_code == 200,
                "live TPP proposal submission failed",
                status=submission_response.status_code,
                body=submission_response.text,
                trip_id=trip_id,
                proposal_id=proposal["proposal_id"],
            )
            submission_payload = submission_response.json()
            execution_id = submission_payload["proposal_state"]["execution_id"]

            status_response = client.post(f"/api/workspace/{trip_id}/proposal/refresh")
            _require(
                status_response.status_code == 200,
                "live TPP proposal status poll failed",
                status=status_response.status_code,
                body=status_response.text,
                trip_id=trip_id,
                proposal_id=proposal["proposal_id"],
                execution_id=execution_id,
            )

            evaluation_request = _prepared_evaluation_request(
                trip_id,
                proposal["proposal_id"],
                execution_id,
            )
            evaluation_response = client.put(
                f"/api/workspace/{trip_id}/proposal/evaluation",
                json={
                    "request": evaluation_request,
                    "response": None,
                    "proposal_version": "proposal-v3",
                    "scenario_id": "scenario-a",
                },
            )
            _require(
                evaluation_response.status_code == 200,
                "live TPP evaluation ingestion failed",
                status=evaluation_response.status_code,
                body=evaluation_response.text,
                trip_id=trip_id,
                proposal_id=proposal["proposal_id"],
            )
            payload = evaluation_response.json()
            return {
                "base_url": base_url,
                "trip_id": trip_id,
                "proposal_id": proposal["proposal_id"],
                "execution_id": payload["proposal_state"]["execution_id"],
                "status_poll": status_response.json()["summary"]["submission_status"],
                "evaluation_status": payload["summary"]["evaluation_result_status"],
            }
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


@contextmanager
def _temporary_database_url(database_url: str) -> Iterator[None]:
    previous_database_url = os.environ.get("TRIP_PLANNER_DATABASE_URL")
    os.environ["TRIP_PLANNER_DATABASE_URL"] = database_url
    try:
        yield
    finally:
        reset_database_state()
        if previous_database_url is None:
            os.environ.pop("TRIP_PLANNER_DATABASE_URL", None)
        else:
            os.environ["TRIP_PLANNER_DATABASE_URL"] = previous_database_url


@contextmanager
def _force_planner_fallback_runtime() -> Iterator[None]:
    """Keep full-product verification independent of live planner model transport."""

    managed_keys = (
        "TRIP_PLANNER_PLANNER_PROVIDER",
        "TRIP_PLANNER_PLANNER_MODEL_PROVIDER",
        "TRIP_PLANNER_PLANNER_MODEL",
        "OPENAI_API_KEY",
    )
    previous = {key: os.environ.get(key) for key in managed_keys}
    for key in managed_keys:
        os.environ.pop(key, None)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_product_journeys(*, live_tpp: str) -> list[CheckResult]:
    with (
        tempfile.TemporaryDirectory(prefix="trip-planner-full-product.") as tmpdir,
        _temporary_database_url(f"sqlite:///{Path(tmpdir) / 'full_product.db'}"),
        _force_planner_fallback_runtime(),
    ):
        reset_database_state()
        ensure_database_ready()
        app = create_app()
        results: list[CheckResult] = []

        with TestClient(app) as client:
            user_id = _signup(client)
            leisure_trip_id = _create_trip(
                client,
                mode="leisure",
                title="Full-product leisure verification",
                region="Seattle",
            )
            leisure_workspace = client.get(f"/api/workspace/{leisure_trip_id}")
            _require(
                leisure_workspace.status_code == 200,
                "leisure workspace load failed",
                status=leisure_workspace.status_code,
                trip_id=leisure_trip_id,
            )
            leisure_payload = leisure_workspace.json()
            comparison = client.get(f"/api/workspace/{leisure_trip_id}/scenarios/compare")
            _require(
                comparison.status_code == 200,
                "scenario comparison failed",
                status=comparison.status_code,
                trip_id=leisure_trip_id,
                route=f"/api/workspace/{leisure_trip_id}/scenarios/compare",
            )
            planner_turn = client.post(
                f"/api/planner/{leisure_trip_id}/turns",
                json={"message": "Compare these scenarios and recommend a next step."},
            )
            _require(
                planner_turn.status_code == 200,
                "planner turn failed",
                status=planner_turn.status_code,
                body=planner_turn.text,
                trip_id=leisure_trip_id,
                route=f"/api/planner/{leisure_trip_id}/turns",
            )
            _assert_runtime_inventory(leisure_payload, trip_id=leisure_trip_id)
            _assert_workspace_scenario_context(leisure_payload, trip_id=leisure_trip_id)
            planner_runtime = _assert_planner_runtime_response(
                planner_turn.json(),
                trip_id=leisure_trip_id,
            )
            results.append(
                CheckResult(
                    "local-leisure-journey",
                    "PASS",
                    {
                        "user_id": user_id,
                        "trip_id": leisure_trip_id,
                        "scenario_id": leisure_payload["runtime_scenario_comparison"][
                            "lead_scenario_id"
                        ],
                        "planner_runtime": planner_runtime,
                        "route_contexts": len(
                            leisure_payload["runtime_scenario_comparison"]["scenarios"]
                        ),
                    },
                )
            )

            business_trip_id = _create_trip(
                client,
                mode="business",
                title="Full-product business verification",
                region="Chicago",
            )
            business_workspace = client.get(f"/api/workspace/{business_trip_id}")
            _require(
                business_workspace.status_code == 200,
                "business workspace load failed",
                status=business_workspace.status_code,
                trip_id=business_trip_id,
            )
            business_payload = business_workspace.json()
            _assert_runtime_inventory(business_payload, trip_id=business_trip_id)
            _assert_workspace_scenario_context(business_payload, trip_id=business_trip_id)
            policy_request = _prepared_policy_request(business_trip_id)
            imported = client.put(
                f"/api/workspace/{business_trip_id}/policy",
                json={
                    "request": policy_request,
                    "response": _fixture("policy", "standard_policy_sync.json")["response"],
                    "source_kind": "tpp_sync",
                    "tags": ["full-product-local"],
                },
            )
            _require(
                imported.status_code == 200,
                "local policy import failed",
                status=imported.status_code,
                body=imported.text,
                trip_id=business_trip_id,
                route=f"/api/workspace/{business_trip_id}/policy",
            )

            proposal = _proposal_payload(business_trip_id)
            submission_request = _prepared_submission_request(
                business_trip_id,
                proposal["proposal_id"],
            )
            submission_response = _fixture("proposal_submit_deferred.json")["response"]
            submitted = client.put(
                f"/api/workspace/{business_trip_id}/proposal",
                json={
                    "proposal": proposal,
                    "request": submission_request,
                    "response": submission_response,
                    "proposal_version": "proposal-v3",
                    "scenario_id": "scenario-a",
                },
            )
            _require(
                submitted.status_code == 200,
                "local proposal submission failed",
                status=submitted.status_code,
                body=submitted.text,
                trip_id=business_trip_id,
                proposal_id=proposal["proposal_id"],
                route=f"/api/workspace/{business_trip_id}/proposal",
            )
            execution_id = submitted.json()["proposal_state"]["execution_id"]

            refresh = client.post(f"/api/workspace/{business_trip_id}/proposal/refresh")
            _require(
                refresh.status_code == 200,
                "local proposal status poll failed",
                status=refresh.status_code,
                body=refresh.text,
                trip_id=business_trip_id,
                proposal_id=proposal["proposal_id"],
                execution_id=execution_id,
                route=f"/api/workspace/{business_trip_id}/proposal/refresh",
            )
            refresh_payload = refresh.json()
            _require(
                refresh_payload["summary"]["submission_status"]
                in {"deferred", "failed", "retry_scheduled"},
                "local proposal status poll did not preserve workspace-visible submission state",
                trip_id=business_trip_id,
                proposal_id=proposal["proposal_id"],
                summary=refresh_payload["summary"],
            )
            evaluation_request = _prepared_evaluation_request(
                business_trip_id,
                proposal["proposal_id"],
                execution_id,
            )
            evaluation_response = _prepared_evaluation_response(
                business_trip_id,
                proposal["proposal_id"],
                execution_id,
            )
            evaluated = client.put(
                f"/api/workspace/{business_trip_id}/proposal/evaluation",
                json={
                    "request": evaluation_request,
                    "response": evaluation_response,
                    "proposal_version": "proposal-v3",
                    "scenario_id": "scenario-a",
                },
            )
            _require(
                evaluated.status_code == 200,
                "local evaluation ingestion failed",
                status=evaluated.status_code,
                body=evaluated.text,
                trip_id=business_trip_id,
                proposal_id=proposal["proposal_id"],
                route=f"/api/workspace/{business_trip_id}/proposal/evaluation",
            )
            evaluation_payload = evaluated.json()
            _require(
                evaluation_payload["summary"]["approval_ready"] is True,
                "business evaluation did not produce approval-ready follow-up state",
                trip_id=business_trip_id,
                proposal_id=proposal["proposal_id"],
            )
            reloaded_business_workspace = client.get(f"/api/workspace/{business_trip_id}")
            _require(
                reloaded_business_workspace.status_code == 200,
                "business workspace reload after evaluation failed",
                status=reloaded_business_workspace.status_code,
                trip_id=business_trip_id,
            )
            reloaded_proposal = reloaded_business_workspace.json()["proposal_state"]
            _require(
                reloaded_proposal["summary"]["follow_up_status"] == "resolved",
                "business workspace did not expose reloaded follow-up state",
                trip_id=business_trip_id,
                proposal_id=proposal["proposal_id"],
                follow_up=reloaded_proposal["summary"].get("follow_up"),
            )
            results.append(
                CheckResult(
                    "local-business-journey",
                    "PASS",
                    {
                        "trip_id": business_trip_id,
                        "proposal_id": proposal["proposal_id"],
                        "evaluation_status": evaluation_payload["summary"][
                            "evaluation_result_status"
                        ],
                        "follow_up_status": evaluation_payload["summary"]["follow_up_status"],
                        "status_poll": refresh_payload["summary"]["submission_status"],
                    },
                )
            )

            map_result = classify_map_prerequisite()
            results.append(map_result)
            if map_result.status == "FAIL":
                raise VerificationFailure(json.dumps(map_result.details, sort_keys=True))

            tpp_status = tpp_prerequisite_status(live_tpp=live_tpp)
            if tpp_status.status == "READY":
                live_details = _run_live_tpp_journey(
                    client,
                    business_trip_id,
                    {key: str(value) for key, value in tpp_status.details.items()},
                )
                results.append(CheckResult("live-tpp", "PASS", live_details))
            else:
                results.append(tpp_status)
                if live_tpp == "required":
                    raise VerificationFailure(json.dumps(tpp_status.details, sort_keys=True))

        return results


def _print_results(results: list[CheckResult]) -> None:
    print("Full-product verification results")
    for result in results:
        print(f"- {result.status} {result.name}: {json.dumps(result.details, sort_keys=True)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-tpp",
        choices=("auto", "off", "required"),
        default="auto",
        help=(
            "Run live Travel-Plan-Permission HTTP checks when configured, skip them, "
            "or require them."
        ),
    )
    parser.add_argument(
        "--skip-frontend-smoke",
        action="store_true",
        help="Skip the live backend/frontend smoke layer and run only product journeys.",
    )
    args = parser.parse_args(argv)
    try:
        results = []
        if not args.skip_frontend_smoke:
            results.append(run_frontend_runtime_smoke())
        results.extend(run_product_journeys(live_tpp=args.live_tpp))
    except VerificationFailure as exc:
        print(f"Full-product verification failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            "Full-product verification failed due to an unexpected error: "
            f"{type(exc).__name__}: {exc}. Check repository/configuration paths "
            "and local service setup, including TPP_REPO_PATH and subprocess working directories.",
            file=sys.stderr,
        )
        return 1
    _print_results(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
