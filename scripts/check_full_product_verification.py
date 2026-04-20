#!/usr/bin/env python3
"""Full-product verification gate for local and preview-oriented checks."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
import json
import os
from pathlib import Path
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


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    details: dict[str, Any]


def _require(condition: bool, message: str, **details: Any) -> None:
    if not condition:
        suffix = f" ({json.dumps(details, sort_keys=True)})" if details else ""
        raise VerificationFailure(f"{message}{suffix}")


def _fixture(*parts: str) -> dict[str, Any]:
    path = REPO_ROOT / "tests" / "fixtures" / "integrations" / "tpp" / Path(*parts)
    return json.loads(path.read_text(encoding="utf-8"))


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
    missing = [
        name
        for name in ("TPP_ACCESS_TOKEN", "TPP_OIDC_PROVIDER")
        if not configured[name]
    ]
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


@contextmanager
def _started_tpp_service(env: dict[str, str]) -> Iterator[tuple[str, subprocess.Popen[bytes] | None]]:
    base_url = env.get("TPP_BASE_URL", "").strip()
    repo_path = env.get("TPP_REPO_PATH", "").strip()
    if base_url:
        yield base_url.rstrip("/"), None
        return

    port = _free_local_port(TPP_PORT)
    base_url = f"http://127.0.0.1:{port}"
    service_env = {
        **os.environ,
        "PYTHONPATH": str(Path(repo_path) / "src"),
        "TPP_BASE_URL": base_url,
        "TPP_AUTH_MODE": "static-token",
        "TPP_ACCESS_TOKEN": env["TPP_ACCESS_TOKEN"],
        "TPP_OIDC_PROVIDER": env["TPP_OIDC_PROVIDER"],
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "travel_plan_permission.http_service",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=repo_path,
        env=service_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_http(f"{base_url}/readyz")
        yield base_url, process
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
            process.kill()
            process.wait(timeout=5)


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
            policy_fixture = _fixture("policy", "standard_policy_sync.json")
            policy_request = policy_fixture["request"]
            policy_request["trip_id"] = trip_id
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
            submission_fixture = _fixture("proposal_submit_deferred.json")
            submission_request = submission_fixture["request"]
            submission_request["trip_id"] = trip_id
            submission_request["proposal_id"] = proposal["proposal_id"]
            submission_request["payload"]["proposal_ref"] = proposal["proposal_id"]
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

            evaluation_fixture = _fixture("results", "approved_evaluation.json")
            evaluation_request = evaluation_fixture["request"]
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
                "evaluation_status": payload["summary"]["evaluation_result_status"],
            }
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def run_product_journeys(*, live_tpp: str) -> list[CheckResult]:
    previous_database_url = os.environ.get("TRIP_PLANNER_DATABASE_URL")
    with tempfile.TemporaryDirectory(prefix="trip-planner-full-product.") as tmpdir:
        os.environ["TRIP_PLANNER_DATABASE_URL"] = f"sqlite:///{Path(tmpdir) / 'full_product.db'}"
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
            _require(comparison.status_code == 200, "scenario comparison failed")
            planner_turn = client.post(
                f"/api/planner/{leisure_trip_id}/turns",
                json={"message": "Compare these scenarios and recommend a next step."},
            )
            _require(planner_turn.status_code == 200, "planner turn failed")
            _require(
                leisure_payload["inventory_summary"]["runtime_state"]["status"] == "ready",
                "leisure inventory runtime was not ready",
                trip_id=leisure_trip_id,
            )
            _require(
                leisure_payload["inventory_summary"]["bundle_count"] > 0,
                "leisure journey produced no source-backed inventory bundles",
                trip_id=leisure_trip_id,
            )
            _require(
                leisure_payload["runtime_scenario_comparison"]["scenarios"],
                "leisure scenario comparison returned no scenarios",
                trip_id=leisure_trip_id,
            )
            _require(
                leisure_payload["inventory_summary"]["source_metadata"]["origin"] == "runtime",
                "leisure workspace did not expose runtime source metadata",
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
                        "planner_runtime": planner_turn.json()["runtime"]["mode"],
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
            _require(
                business_payload["runtime_scenario_comparison"]["scenarios"],
                "business scenario comparison returned no scenarios",
                trip_id=business_trip_id,
            )
            policy_fixture = _fixture("policy", "standard_policy_sync.json")
            policy_fixture["request"]["trip_id"] = business_trip_id
            imported = client.put(
                f"/api/workspace/{business_trip_id}/policy",
                json={
                    "request": policy_fixture["request"],
                    "response": policy_fixture["response"],
                    "source_kind": "tpp_sync",
                    "tags": ["full-product-local"],
                },
            )
            _require(imported.status_code == 200, "local policy import failed")

            proposal = _proposal_payload(business_trip_id)
            submission_fixture = _fixture("proposal_submit_deferred.json")
            submission_fixture["request"]["trip_id"] = business_trip_id
            submission_fixture["request"]["proposal_id"] = proposal["proposal_id"]
            submission_fixture["request"]["payload"]["proposal_ref"] = proposal["proposal_id"]
            submitted = client.put(
                f"/api/workspace/{business_trip_id}/proposal",
                json={
                    "proposal": proposal,
                    "request": submission_fixture["request"],
                    "response": submission_fixture["response"],
                    "proposal_version": "proposal-v3",
                    "scenario_id": "scenario-a",
                },
            )
            _require(submitted.status_code == 200, "local proposal submission failed")

            evaluation_fixture = _fixture("results", "approved_evaluation.json")
            evaluation_fixture["request"]["trip_id"] = business_trip_id
            evaluation_fixture["request"]["proposal_id"] = proposal["proposal_id"]
            evaluation_fixture["response"]["result_payload"]["trip_id"] = business_trip_id
            evaluation_fixture["response"]["result_payload"]["proposal_id"] = proposal[
                "proposal_id"
            ]
            evaluation_fixture["response"]["result_payload"]["evaluation_result"][
                "proposal_id"
            ] = proposal["proposal_id"]
            evaluated = client.put(
                f"/api/workspace/{business_trip_id}/proposal/evaluation",
                json={
                    "request": evaluation_fixture["request"],
                    "response": evaluation_fixture["response"],
                    "proposal_version": "proposal-v3",
                    "scenario_id": "scenario-a",
                },
            )
            _require(evaluated.status_code == 200, "local evaluation ingestion failed")
            evaluation_payload = evaluated.json()
            _require(
                evaluation_payload["summary"]["approval_ready"] is True,
                "business evaluation did not produce approval-ready follow-up state",
                trip_id=business_trip_id,
                proposal_id=proposal["proposal_id"],
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
                if live_tpp == "required" and tpp_status.status != "PASS":
                    raise VerificationFailure(json.dumps(tpp_status.details, sort_keys=True))

        reset_database_state()
        if previous_database_url is None:
            os.environ.pop("TRIP_PLANNER_DATABASE_URL", None)
        else:
            os.environ["TRIP_PLANNER_DATABASE_URL"] = previous_database_url
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
    args = parser.parse_args(argv)
    try:
        results = run_product_journeys(live_tpp=args.live_tpp)
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
