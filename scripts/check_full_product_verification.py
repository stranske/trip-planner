#!/usr/bin/env python3
"""Full-product verification gate for local and preview-oriented checks."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib import request as urllib_request

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from httpx import HTTPError  # noqa: E402

from trip_planner.app.main import create_app  # noqa: E402
from trip_planner.app.services.planner_runtime_config import (  # noqa: E402
    build_planner_runtime_config,
)
from trip_planner.persistence.db import (  # noqa: E402
    ensure_database_ready,
    reset_database_state,
)

DEFAULT_TPP_REPO_PATH = REPO_ROOT.parent / "Travel-Plan-Permission"
DEFAULT_TPP_ORGANIZATION_ID = "org-acme"
TPP_PORT = 8765
EXPECTED_BUSINESS_EVALUATION_STATUS = "non_compliant"
_SUPPORTED_LINEAGE_LABELS = frozenset(
    {"compliant_first", "exception_nearest", "baseline", "fallback"}
)
_EVALUATION_FIXTURE_BY_STATUS = {
    "compliant": "approved_evaluation.json",
    "non_compliant": "non_compliant_evaluation.json",
}


def _resolved_tpp_organization_id(env: Mapping[str, str] | None = None) -> str:
    if env is not None:
        configured = str(env.get("TPP_ORGANIZATION_ID") or "").strip()
        if configured:
            return configured
    env_configured = os.environ.get("TPP_ORGANIZATION_ID", "").strip()
    if env_configured:
        return env_configured
    return DEFAULT_TPP_ORGANIZATION_ID


def _evaluation_fixture_name(expected_status: str) -> str:
    fixture_name = _EVALUATION_FIXTURE_BY_STATUS.get(expected_status)
    if fixture_name is None:
        raise VerificationFailure(
            json.dumps(
                {
                    "expected_status": expected_status,
                    "supported_statuses": sorted(_EVALUATION_FIXTURE_BY_STATUS),
                },
                sort_keys=True,
            )
        )
    return fixture_name


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


def _assert_live_tpp_record_invariants(
    live_details: Mapping[str, Any],
    *,
    expected_evaluation_status: str,
) -> None:
    compatibility_control = live_details.get("compatibility_control")
    if isinstance(compatibility_control, Mapping):
        _require(
            compatibility_control.get("offline_fixture_journey_retained") is True,
            "live TPP compatibility control did not retain the offline fixture journey",
            compatibility_control=dict(compatibility_control),
            trip_id=live_details.get("trip_id"),
        )
        _require(
            compatibility_control.get("saved_scenario_lineage_preserved") is True,
            "live TPP compatibility control did not preserve saved scenario lineage",
            compatibility_control=dict(compatibility_control),
            trip_id=live_details.get("trip_id"),
        )
        if "compatible_with_planner_cache" in compatibility_control:
            _require(
                compatibility_control.get("compatible_with_planner_cache") is True,
                "live TPP compatibility control reported incompatible planner cache",
                compatibility_control=dict(compatibility_control),
                trip_id=live_details.get("trip_id"),
            )
        if "organization_id" in compatibility_control and "organization_id" in live_details:
            _require(
                compatibility_control.get("organization_id") == live_details.get("organization_id"),
                "live TPP compatibility control organization disagreed with live organization",
                compatibility_control=dict(compatibility_control),
                live_organization_id=live_details.get("organization_id"),
                trip_id=live_details.get("trip_id"),
            )
    external_ids = live_details.get("external_ids")
    if isinstance(external_ids, Mapping):
        for field_name in ("policy_id", "execution_id", "evaluation_id"):
            _require(
                bool(str(external_ids.get(field_name) or "").strip()),
                "live TPP verification did not record required external identifier",
                field=field_name,
                external_ids=dict(external_ids),
                trip_id=live_details.get("trip_id"),
            )
    verdict_readback = live_details.get("verdict_readback")
    if isinstance(verdict_readback, Mapping):
        _require(
            verdict_readback.get("status") == expected_evaluation_status,
            "live TPP persisted verdict readback did not match the expected outcome",
            expected_evaluation_status=expected_evaluation_status,
            verdict_readback=dict(verdict_readback),
            trip_id=live_details.get("trip_id"),
        )
        if isinstance(external_ids, Mapping):
            _require(
                verdict_readback.get("evaluation_id") == external_ids.get("evaluation_id"),
                "live TPP persisted verdict readback evaluation_id disagreed with external IDs",
                external_ids=dict(external_ids),
                verdict_readback=dict(verdict_readback),
                trip_id=live_details.get("trip_id"),
            )
        if "scenario_id" in live_details:
            _require(
                verdict_readback.get("scenario_id") == live_details.get("scenario_id"),
                "live TPP persisted verdict readback scenario_id disagreed with submitted scenario",
                expected_scenario_id=live_details.get("scenario_id"),
                verdict_readback=dict(verdict_readback),
                trip_id=live_details.get("trip_id"),
            )
        _require(
            bool(str(verdict_readback.get("saved_scenario_id") or "").strip())
            and bool(str(verdict_readback.get("source_version_id") or "").strip()),
            "live TPP persisted verdict readback did not retain saved scenario lineage",
            verdict_readback=dict(verdict_readback),
            trip_id=live_details.get("trip_id"),
        )
    native_transitions = live_details.get("native_transitions")
    if isinstance(native_transitions, Mapping):
        if expected_evaluation_status == "compliant":
            _require(
                "reoptimize" not in native_transitions,
                "live TPP compliant control unexpectedly recorded a reoptimize transition",
                native_transitions=dict(native_transitions),
                trip_id=live_details.get("trip_id"),
            )
        else:
            _require(
                bool(str(native_transitions.get("reoptimize") or "").strip())
                and live_details.get("follow_up_status") == "reoptimized",
                "live TPP non-compliant journey did not record persisted reoptimization",
                native_transitions=dict(native_transitions),
                follow_up_status=live_details.get("follow_up_status"),
                trip_id=live_details.get("trip_id"),
            )


def _assert_business_verification_outcomes(
    local_details: Mapping[str, Any],
    *,
    expected_evaluation_status: str,
    live_details: Mapping[str, Any] | None = None,
    require_status_poll: bool = True,
) -> None:
    """Assert the business journey's semantic, not merely transport, contract."""

    local_status = local_details["evaluation_status"]
    _require(
        local_status == expected_evaluation_status,
        "local business evaluation did not match the expected outcome",
        expected_evaluation_status=expected_evaluation_status,
        actual_evaluation_status=local_status,
        trip_id=local_details.get("trip_id"),
        proposal_id=local_details.get("proposal_id"),
    )
    if require_status_poll:
        _require(
            local_details["status_poll"] != "failed",
            "local business proposal status poll reported failure",
            status_poll=local_details["status_poll"],
            trip_id=local_details.get("trip_id"),
            proposal_id=local_details.get("proposal_id"),
        )
    if live_details is None:
        return

    live_status = live_details["evaluation_status"]
    # TPP truthfully marks a policy-blocked proposal execution as failed. That
    # expected negative journey is distinct from a failed status transport.
    live_error = live_details.get("submission_error") or {}
    expected_policy_block = (
        expected_evaluation_status == "non_compliant"
        and live_status == "non_compliant"
        and live_details.get("evaluation_transport_status") == "succeeded"
        and live_details.get("submission_outcome") == "blocked_by_policy"
        and live_error.get("category") == "policy"
        and live_error.get("code") == "proposal_blocked_by_policy"
    )
    _require(
        live_details["status_poll"] != "failed" or expected_policy_block,
        "live TPP proposal status poll reported failure",
        status_poll=live_details["status_poll"],
        trip_id=live_details.get("trip_id"),
        proposal_id=live_details.get("proposal_id"),
    )
    _require(
        local_details["proposal_id"] == live_details["proposal_id"],
        "local and live policy checks used different proposals",
        local_proposal_id=local_details["proposal_id"],
        live_proposal_id=live_details["proposal_id"],
    )
    _require(
        local_status == live_status,
        "local and live policy evaluation statuses disagree",
        local_evaluation_status=local_status,
        live_evaluation_status=live_status,
        trip_id=local_details.get("trip_id"),
        proposal_id=local_details["proposal_id"],
    )
    _require(
        live_status == expected_evaluation_status,
        "live TPP evaluation did not match the expected outcome",
        expected_evaluation_status=expected_evaluation_status,
        actual_evaluation_status=live_status,
        trip_id=live_details.get("trip_id"),
        proposal_id=live_details.get("proposal_id"),
    )
    _assert_live_tpp_record_invariants(
        live_details,
        expected_evaluation_status=expected_evaluation_status,
    )


def _fixture(*parts: str) -> dict[str, Any]:
    path = REPO_ROOT / "tests" / "fixtures" / "integrations" / "tpp" / Path(*parts)
    return json.loads(path.read_text(encoding="utf-8"))


def run_frontend_runtime_smoke() -> CheckResult:
    command = [
        str(REPO_ROOT / "scripts" / "check_full_stack_runtime.sh"),
        "--smoke-only",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
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


def _create_trip(
    client: TestClient,
    *,
    mode: str,
    title: str,
    region: str,
    traveler_count: int | None = None,
    duration_days: int = 3,
) -> str:
    start_date = date.today() + timedelta(days=45)
    end_date = start_date + timedelta(days=duration_days - 1)
    party_count = traveler_count if traveler_count is not None else (3 if mode == "business" else 1)
    response = client.post(
        "/api/trips",
        json={
            "title": title,
            "summary": f"Full-product verification for {title}.",
            "mode": mode,
            "trip_frame": {
                "origin": "Seattle",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "duration_days": duration_days,
                "primary_regions": [region],
                "traveler_party": {
                    "kind": "team" if party_count > 1 else "solo",
                    "traveler_count": party_count,
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
    trip_id: str,
    proposal_id: str,
    execution_id: str,
    *,
    fixture_name: str = "approved_evaluation.json",
) -> dict[str, Any]:
    request_payload = copy.deepcopy(_fixture("results", fixture_name)["request"])
    request_payload["trip_id"] = trip_id
    request_payload["proposal_id"] = proposal_id
    request_payload["payload"]["execution_id"] = execution_id
    return request_payload


def _prepared_evaluation_response(
    trip_id: str,
    proposal_id: str,
    execution_id: str,
    *,
    fixture_name: str = "approved_evaluation.json",
) -> dict[str, Any]:
    response_payload = copy.deepcopy(_fixture("results", fixture_name)["response"])
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
    _require(
        bool(scenarios),
        "workspace scenario search returned no scenarios",
        trip_id=trip_id,
    )
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
            {
                "provider_state": "loading",
                "message": "Provider adapter has not become ready.",
            },
        )
    return CheckResult(
        "map-provider",
        "FAIL",
        {
            "provider_state": provider_state,
            "message": "Configured map provider reported an error.",
        },
    )


def classify_planner_llm_prerequisite(
    env: Mapping[str, str] | None = None,
) -> CheckResult:
    runtime = build_planner_runtime_config(os.environ if env is None else env)
    details = {
        "data_zone": runtime.data_zone,
        "mode": runtime.mode,
        "provider": runtime.provider,
        "model": runtime.model,
        "llm_status": runtime.llm_status,
        "fallback_reason": runtime.fallback_reason,
    }
    if runtime.llm_status == "blocked":
        details["remediation"] = (
            "Set TRIP_PLANNER_OPENAI_AUTHORIZED_ENDPOINT only for an approved no-train "
            "OpenAI endpoint with the outbound prompt redaction hook enabled, or leave the "
            "planner in deterministic fallback mode."
        )
        return CheckResult("planner-llm", "BLOCKED", details)
    if runtime.mode == "model":
        return CheckResult("planner-llm", "READY", details)
    return CheckResult("planner-llm", "SKIPPED", details)


_REMEDIATION_OFF = (
    "Re-run with `--live-tpp auto` (or `required`) after setting `TPP_BASE_URL` or "
    "`TPP_REPO_PATH` to opt into live verification."
)
_REMEDIATION_MISSING_TRANSPORT = (
    "Set TPP_BASE_URL (for an externally managed service) or TPP_REPO_PATH (for a "
    "sibling Travel-Plan-Permission checkout)."
)
_REMEDIATION_MISSING_AUTH = (
    "Set TPP_ACCESS_TOKEN and TPP_OIDC_PROVIDER for the configured transport target."
)


def _classify_invalid_repo_path(value: str) -> dict[str, str]:
    path = Path(value)
    if not path.exists():
        kind = "missing"
        message = f"TPP_REPO_PATH `{value}` does not exist."
    elif not path.is_dir():
        kind = "not-a-directory"
        message = f"TPP_REPO_PATH `{value}` exists but is not a directory."
    else:  # pragma: no cover - caller already validated reachability
        kind = "unreadable"
        message = f"TPP_REPO_PATH `{value}` is not a usable Travel-Plan-Permission checkout."
    return {"path": value, "kind": kind, "message": message}


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
        return CheckResult(
            "live-tpp",
            "SKIPPED",
            {"mode": "off", "remediation": _REMEDIATION_OFF},
        )
    if live_tpp == "auto" and (not explicit or not has_transport_target):
        return CheckResult(
            "live-tpp",
            "SKIPPED",
            {
                "missing_env": "TPP_BASE_URL or TPP_REPO_PATH",
                "default_repo_path": str(default_repo_path),
                "remediation": _REMEDIATION_MISSING_TRANSPORT,
            },
        )
    missing = [name for name in ("TPP_ACCESS_TOKEN", "TPP_OIDC_PROVIDER") if not configured[name]]
    invalid_path: dict[str, str] = {}
    invalid_path_detail: dict[str, str] = {}
    if not configured["TPP_BASE_URL"] and not configured["TPP_REPO_PATH"]:
        if live_tpp == "required" and default_repo_path.is_dir():
            configured["TPP_REPO_PATH"] = str(default_repo_path)
        else:
            missing.append("TPP_BASE_URL or TPP_REPO_PATH")
    if configured["TPP_REPO_PATH"]:
        repo_path = Path(configured["TPP_REPO_PATH"])
        if not repo_path.exists() or not repo_path.is_dir():
            invalid_path["TPP_REPO_PATH"] = configured["TPP_REPO_PATH"]
            invalid_path_detail = _classify_invalid_repo_path(configured["TPP_REPO_PATH"])
    if missing or invalid_path:
        details: dict[str, Any] = {}
        remediations: list[str] = []
        if missing:
            details["missing_env"] = sorted(set(missing))
            if "TPP_BASE_URL or TPP_REPO_PATH" in missing:
                remediations.append(_REMEDIATION_MISSING_TRANSPORT)
            if any(name in missing for name in ("TPP_ACCESS_TOKEN", "TPP_OIDC_PROVIDER")):
                remediations.append(_REMEDIATION_MISSING_AUTH)
        if invalid_path:
            details["invalid_path"] = invalid_path
            details["invalid_path_detail"] = invalid_path_detail
            remediations.append(
                "Set TPP_REPO_PATH to a sibling Travel-Plan-Permission checkout directory, "
                "or unset it and use TPP_BASE_URL for an externally managed service."
            )
        if remediations:
            details["remediation"] = " ".join(remediations)
        return CheckResult("live-tpp", "BLOCKED", details)
    return CheckResult(
        "live-tpp",
        "READY",
        {
            **configured,
            **(
                {"TPP_ORGANIZATION_ID": env_map["TPP_ORGANIZATION_ID"].strip()}
                if env_map.get("TPP_ORGANIZATION_ID", "").strip()
                else {}
            ),
        },
    )


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
        except Exception as exc:  # noqa: BLE001 # pragma: no cover - exercised by integration use
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
        (
            "Cannot auto-start TPP: expected either "
            f"{venv_python} or `uv run --directory {repo_path} python` "
            "(with uv.lock present and uv installed)."
        ),
        venv_python=str(venv_python),
        uv_lock=str(repo_path / "uv.lock"),
        remediation=(
            f"Install TPP dependencies into {repo_path}/.venv, install uv for the repo's "
            "uv.lock path, or set TPP_BASE_URL to skip auto-start."
        ),
    )


def _tail_file(path: Path, *, line_count: int = 50, max_bytes: int = 64 * 1024) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        start = max(size - max_bytes - 1, 0)
        handle.seek(start)
        text = handle.read(max_bytes + 1).decode("utf-8", errors="replace")
    if start > 0:
        first_newline = text.find("\n")
        if first_newline == -1:
            return ""
        text = text[first_newline + 1 :]
    lines = text.splitlines()
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
        "TPP_ORGANIZATION_ID": _resolved_tpp_organization_id(env),
    }
    # These files must remain addressable after their handles close so readiness failures can tail them.
    stdout_file = tempfile.NamedTemporaryFile(  # noqa: SIM115
        prefix="tpp-service-", suffix=".stdout", delete=False
    )
    stderr_file = tempfile.NamedTemporaryFile(  # noqa: SIM115
        prefix="tpp-service-", suffix=".stderr", delete=False
    )
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
    try:
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            env=service_env,
            stdout=stdout_file,
            stderr=stderr_file,
        )
    except Exception:
        stdout_file.close()
        stderr_file.close()
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)
        raise
    else:
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
                interpreter=shlex.join(interpreter),
                command=shlex.join(command),
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


def _matching_saved_scenario_version(
    saved_scenarios: list[dict[str, Any]],
    *,
    selected_scenario_id: str,
    current_saved_scenario_id: str | None,
) -> dict[str, Any] | None:
    ordered = sorted(
        saved_scenarios,
        key=lambda saved: (
            saved.get("saved_scenario_id") != selected_scenario_id,
            saved.get("saved_scenario_id") != current_saved_scenario_id,
        ),
    )
    for saved in ordered:
        current_version_id = saved.get("current_version_id")
        for version in saved.get("versions") or []:
            if not isinstance(version, dict) or version.get("version_id") != current_version_id:
                continue
            refs = version.get("snapshot_refs")
            if not isinstance(refs, dict):
                continue
            if selected_scenario_id not in (
                saved.get("saved_scenario_id"),
                refs.get("itinerary_scenario_id"),
            ):
                continue
            if version.get("label") in _SUPPORTED_LINEAGE_LABELS:
                return dict(version)
    return None


def _ensure_live_saved_scenario_lineage(
    client: TestClient,
    *,
    trip_id: str,
    policy_state_id: str,
) -> tuple[str, dict[str, Any]]:
    workspace_response = client.get(f"/api/workspace/{trip_id}?debug=true")
    _require(
        workspace_response.status_code == 200,
        "live TPP workspace load before submission failed",
        status=workspace_response.status_code,
        body=workspace_response.text,
        trip_id=trip_id,
        route=f"/api/workspace/{trip_id}?debug=true",
    )
    workspace_payload = workspace_response.json()
    runtime_comparison = dict(workspace_payload.get("runtime_scenario_comparison") or {})
    scenario_rows = [
        row for row in (runtime_comparison.get("scenarios") or []) if isinstance(row, dict)
    ]
    _require(
        bool(scenario_rows),
        "live TPP workspace has no runtime scenarios for native submission",
        trip_id=trip_id,
    )
    lead_id = runtime_comparison.get("lead_scenario_id")
    lead_row = next(
        (row for row in scenario_rows if row.get("scenario_id") == lead_id),
        scenario_rows[0],
    )
    selected_scenario_id = str(lead_row["scenario_id"])
    saved_scenarios = [
        item for item in (workspace_payload.get("saved_scenarios") or []) if isinstance(item, dict)
    ]
    _require(
        bool(saved_scenarios),
        "live TPP workspace has no saved scenarios for lineage",
        trip_id=trip_id,
    )
    matching_version = _matching_saved_scenario_version(
        saved_scenarios,
        selected_scenario_id=selected_scenario_id,
        current_saved_scenario_id=dict(workspace_payload.get("session") or {}).get(
            "current_saved_scenario_id"
        ),
    )
    if matching_version is not None:
        return selected_scenario_id, matching_version

    base_versions = [
        version
        for version in (saved_scenarios[0].get("versions") or [])
        if isinstance(version, dict)
    ]
    base_refs = dict((base_versions[0].get("snapshot_refs") if base_versions else None) or {})
    base_refs["itinerary_scenario_id"] = selected_scenario_id
    base_refs["policy_state_id"] = policy_state_id
    saved_response = client.post(
        f"/api/trips/{trip_id}/saved-scenarios",
        json={
            "title": "Selected business route",
            "label": "compliant_first",
            "snapshot_refs": base_refs,
        },
    )
    _require(
        saved_response.status_code == 201,
        "live TPP saved scenario materialization failed",
        status=saved_response.status_code,
        body=saved_response.text,
        trip_id=trip_id,
        scenario_id=selected_scenario_id,
        route=f"/api/trips/{trip_id}/saved-scenarios",
    )
    saved_scenario = dict(saved_response.json().get("saved_scenario") or {})
    current_version_id = saved_scenario.get("current_version_id")
    active_version = next(
        (
            dict(version)
            for version in (saved_scenario.get("versions") or [])
            if isinstance(version, dict) and version.get("version_id") == current_version_id
        ),
        None,
    )
    _require(
        active_version is not None,
        "live TPP saved scenario is missing active version lineage",
        trip_id=trip_id,
        scenario_id=selected_scenario_id,
        saved_scenario_id=saved_scenario.get("saved_scenario_id"),
    )
    assert active_version is not None
    return selected_scenario_id, active_version


def _assert_native_live_tpp_route_order(
    *,
    trip_id: str,
    observed_transitions: list[tuple[str, str]],
    expected_evaluation_status: str = EXPECTED_BUSINESS_EVALUATION_STATUS,
) -> None:
    forbidden_put_routes = {
        ("PUT", f"/api/workspace/{trip_id}/policy"),
        ("PUT", f"/api/workspace/{trip_id}/proposal"),
        ("PUT", f"/api/workspace/{trip_id}/proposal/evaluation"),
    }
    bypassed_puts = [route for route in observed_transitions if route in forbidden_put_routes]
    _require(
        not bypassed_puts,
        "live TPP journey bypassed native transition with caller-staged PUT",
        trip_id=trip_id,
        bypassed_routes=[f"{method} {path}" for method, path in bypassed_puts],
    )
    reoptimize_route = ("POST", f"/api/workspace/{trip_id}/proposal/reoptimize")
    if expected_evaluation_status == "compliant":
        _require(
            reoptimize_route not in observed_transitions,
            "live TPP compliant control unexpectedly invoked reoptimization",
            trip_id=trip_id,
            observed_transitions=[f"{method} {path}" for method, path in observed_transitions],
        )
        required_native_routes: tuple[tuple[str, str], ...] = (
            ("POST", f"/api/workspace/{trip_id}/policy/sync"),
            ("POST", f"/api/workspace/{trip_id}/proposal/submit"),
            ("POST", f"/api/workspace/{trip_id}/proposal/refresh"),
            ("GET", f"/api/workspace/{trip_id}/proposal"),
        )
    else:
        required_native_routes = (
            ("POST", f"/api/workspace/{trip_id}/policy/sync"),
            ("POST", f"/api/workspace/{trip_id}/proposal/submit"),
            ("POST", f"/api/workspace/{trip_id}/proposal/refresh"),
            ("GET", f"/api/workspace/{trip_id}/proposal"),
            reoptimize_route,
            ("GET", f"/api/workspace/{trip_id}/proposal"),
        )
    cursor = 0
    for expected_route in required_native_routes:
        try:
            cursor = observed_transitions.index(expected_route, cursor) + 1
        except ValueError as exc:
            raise VerificationFailure(
                "live TPP journey bypassed required native transition",
                trip_id=trip_id,
                missing_transition=f"{expected_route[0]} {expected_route[1]}",
                observed_transitions=[f"{method} {path}" for method, path in observed_transitions],
            ) from exc


def _assert_native_live_tpp_policy_state(
    *,
    trip_id: str,
    configured_organization_id: str,
    policy_state: Mapping[str, Any],
    policy_summary: Mapping[str, Any] | None = None,
) -> str:
    policy_id = str(policy_state.get("policy_id") or "")
    policy_version = str(policy_state.get("policy_version") or "")
    policy_request_id = str(policy_state.get("source_request_id") or "")
    _require(
        policy_state.get("organization_id") == configured_organization_id,
        "live TPP policy sync did not use the configured organization",
        trip_id=trip_id,
        expected_organization_id=configured_organization_id,
        actual_organization_id=policy_state.get("organization_id"),
    )
    _require(
        bool(policy_id) and bool(policy_version),
        "live TPP policy sync did not return external policy identifiers",
        trip_id=trip_id,
        policy_id=policy_id,
        policy_version=policy_version,
    )
    _require(
        policy_state.get("source_kind") == "tpp_sync"
        and policy_request_id.startswith("policy-sync:")
        and policy_state.get("source_correlation_id") == f"policy-sync:{trip_id}"
        and "workspace-sync" in list(policy_state.get("tags") or []),
        "live TPP policy state was not produced by native POST policy sync",
        trip_id=trip_id,
        source_kind=policy_state.get("source_kind"),
        source_request_id=policy_request_id,
        source_correlation_id=policy_state.get("source_correlation_id"),
        tags=policy_state.get("tags"),
    )
    if policy_summary is not None:
        _require(
            policy_summary.get("status") != "stored_policy_fallback",
            "live TPP policy sync fell back to stored policy instead of live sync",
            trip_id=trip_id,
            policy_summary=dict(policy_summary),
        )
        _require(
            policy_summary.get("compatible_with_planner_cache") is True,
            "live TPP policy sync reported incompatible planner cache",
            trip_id=trip_id,
            policy_summary=dict(policy_summary),
        )
        _require(
            policy_summary.get("sync_status") == "current"
            and policy_summary.get("is_stale") is not True,
            "live TPP policy sync did not return a current policy snapshot",
            trip_id=trip_id,
            policy_summary=dict(policy_summary),
        )
    return policy_id


def _assert_native_live_tpp_submission_state(
    *,
    trip_id: str,
    configured_organization_id: str,
    policy_id: str,
    selected_scenario_id: str,
    expected_source_version: Mapping[str, Any],
    submitted_state: Mapping[str, Any],
) -> str:
    submitted_proposal = dict(submitted_state.get("proposal") or {})
    submitted_record = dict(submitted_state.get("submission") or {})
    submission_request_id = str(submitted_record.get("request_id") or "")
    execution_id = str(submitted_state.get("execution_id") or "")
    _require(
        submitted_state.get("organization_id") == configured_organization_id,
        "live TPP proposal submission did not use the configured organization",
        trip_id=trip_id,
        expected_organization_id=configured_organization_id,
        actual_organization_id=submitted_state.get("organization_id"),
    )
    _require(
        submitted_state.get("scenario_id") == selected_scenario_id
        and submitted_proposal.get("source_version") == dict(expected_source_version),
        "live TPP proposal submission did not preserve saved scenario lineage",
        trip_id=trip_id,
        expected_scenario_id=selected_scenario_id,
        actual_scenario_id=submitted_state.get("scenario_id"),
        expected_source_version=dict(expected_source_version),
        actual_source_version=submitted_proposal.get("source_version"),
    )
    _require(
        submitted_proposal.get("constraint_set_id") == policy_id
        and submission_request_id.startswith("submit-proposal:")
        and submitted_record.get("correlation_id") == f"submit-proposal:{trip_id}"
        and bool(execution_id)
        and execution_id != "exec-001",
        "live TPP proposal submission did not record native external submission identifiers",
        trip_id=trip_id,
        constraint_set_id=submitted_proposal.get("constraint_set_id"),
        expected_policy_id=policy_id,
        submission_request_id=submission_request_id,
        correlation_id=submitted_record.get("correlation_id"),
        execution_id=execution_id,
    )
    return execution_id


def _assert_native_live_tpp_verdict_readback(
    *,
    trip_id: str,
    configured_organization_id: str,
    execution_id: str,
    selected_scenario_id: str,
    expected_source_version: Mapping[str, Any],
    expected_evaluation_status: str,
    readback_state: Mapping[str, Any],
    readback_summary: Mapping[str, Any],
) -> None:
    readback_proposal = dict(readback_state.get("proposal") or {})
    readback_evaluation = dict(readback_state.get("evaluation") or {})
    readback_evaluation_result = dict(readback_evaluation.get("evaluation_result") or {})
    readback_linkage = dict(readback_evaluation.get("linkage") or {})
    evaluation_id = str(readback_evaluation_result.get("evaluation_id") or "")
    expected_follow_up_status = (
        "resolved" if expected_evaluation_status == "compliant" else "reoptimization_required"
    )
    _require(
        readback_state.get("organization_id") == configured_organization_id
        and readback_state.get("execution_id") == execution_id
        and readback_state.get("scenario_id") == selected_scenario_id
        and readback_proposal.get("source_version") == dict(expected_source_version),
        "live TPP persisted proposal readback did not match the submitted scenario lineage",
        trip_id=trip_id,
        expected_organization_id=configured_organization_id,
        actual_organization_id=readback_state.get("organization_id"),
        expected_execution_id=execution_id,
        actual_execution_id=readback_state.get("execution_id"),
        expected_scenario_id=selected_scenario_id,
        actual_scenario_id=readback_state.get("scenario_id"),
        expected_source_version=dict(expected_source_version),
        actual_source_version=readback_proposal.get("source_version"),
    )
    _require(
        bool(evaluation_id)
        and str(readback_evaluation.get("request_id") or "").startswith("fetch_evaluation_result:")
        and readback_evaluation.get("correlation_id") == f"submit-proposal:{trip_id}"
        and readback_linkage.get("scenario_id") == selected_scenario_id
        and readback_linkage.get("organization_id") == configured_organization_id
        and readback_linkage.get("execution_id") == execution_id
        and readback_evaluation_result.get("status") == expected_evaluation_status
        and readback_summary.get("evaluation_result_status") == expected_evaluation_status
        and readback_summary.get("follow_up_status") == expected_follow_up_status,
        "live TPP persisted verdict readback did not match native evaluation and scenario lineage",
        trip_id=trip_id,
        evaluation_id=evaluation_id,
        evaluation_request_id=readback_evaluation.get("request_id"),
        evaluation_correlation_id=readback_evaluation.get("correlation_id"),
        linkage=readback_linkage,
        expected_evaluation_status=expected_evaluation_status,
        actual_evaluation_status=readback_evaluation_result.get("status"),
        expected_follow_up_status=expected_follow_up_status,
        actual_follow_up_status=readback_summary.get("follow_up_status"),
    )


def _assert_native_live_tpp_reoptimization_readback(
    *,
    trip_id: str,
    evaluation_id: str,
    expected_source_version: Mapping[str, Any],
    expected_evaluation_status: str,
    reoptimized_state: Mapping[str, Any],
    reoptimized_summary: Mapping[str, Any],
) -> dict[str, Any]:
    reoptimized_evaluation = dict(reoptimized_state.get("evaluation") or {})
    reoptimized_result = dict(reoptimized_evaluation.get("evaluation_result") or {})
    follow_up = dict(reoptimized_state.get("follow_up") or {})
    raw_plan = follow_up.get("reoptimization_plan")
    plan = dict(raw_plan) if isinstance(raw_plan, Mapping) else {}
    plan_source_version = dict(plan.get("source_version") or {})
    expected_source_version_id = str(expected_source_version.get("version_id") or "")
    _require(
        reoptimized_result.get("evaluation_id") == evaluation_id
        and reoptimized_result.get("status") == expected_evaluation_status
        and reoptimized_summary.get("evaluation_result_status") == expected_evaluation_status,
        "live TPP persisted reoptimization readback did not preserve pre-action verdict",
        trip_id=trip_id,
        expected_evaluation_id=evaluation_id,
        actual_evaluation_id=reoptimized_result.get("evaluation_id"),
        expected_evaluation_status=expected_evaluation_status,
        actual_evaluation_status=reoptimized_result.get("status"),
        summary_evaluation_status=reoptimized_summary.get("evaluation_result_status"),
    )
    _require(
        follow_up.get("status") == "reoptimized"
        and reoptimized_summary.get("follow_up_status") == "reoptimized"
        and bool(plan)
        and bool(str(plan.get("target_title") or "").strip())
        and bool(str(plan.get("reaction_kind") or "").strip())
        and bool(expected_source_version_id)
        and plan_source_version.get("version_id") == expected_source_version_id
        and plan_source_version == dict(expected_source_version),
        "live TPP persisted reoptimization readback did not retain plan and source lineage",
        trip_id=trip_id,
        follow_up_status=follow_up.get("status"),
        summary_follow_up_status=reoptimized_summary.get("follow_up_status"),
        reoptimization_plan=plan,
        expected_source_version_id=expected_source_version_id,
        actual_source_version_id=plan_source_version.get("version_id"),
    )
    return plan


def _normalize_public_reoptimization_plan(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _normalize_public_reoptimization_plan(item)
            for key, item in value.items()
            if key not in {"policy_state_id", "proposal_state_id"}
        }
    if isinstance(value, list):
        return [_normalize_public_reoptimization_plan(item) for item in value]
    return value


def _execute_live_tpp_reoptimization(
    client: TestClient,
    *,
    trip_id: str,
    proposal_id: str,
    expected_evaluation_status: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    reoptimize_response = client.post(
        f"/api/workspace/{trip_id}/proposal/reoptimize",
        json={},
    )
    _require(
        reoptimize_response.status_code == 200,
        "live TPP proposal reoptimization failed",
        status=reoptimize_response.status_code,
        body=reoptimize_response.text,
        trip_id=trip_id,
        proposal_id=proposal_id,
        route=f"/api/workspace/{trip_id}/proposal/reoptimize",
    )
    reoptimized_readback_response = client.get(f"/api/workspace/{trip_id}/proposal")
    _require(
        reoptimized_readback_response.status_code == 200,
        "live TPP persisted reoptimized proposal readback failed",
        status=reoptimized_readback_response.status_code,
        body=reoptimized_readback_response.text,
        trip_id=trip_id,
        proposal_id=proposal_id,
        route=f"/api/workspace/{trip_id}/proposal",
    )
    reoptimized_payload = reoptimized_readback_response.json()
    reoptimized_state = dict(reoptimized_payload.get("proposal_state") or {})
    reoptimized_summary = dict(reoptimized_payload.get("summary") or {})
    reoptimized_plan = dict(reoptimized_state.get("follow_up") or {}).get("reoptimization_plan")
    reloaded_workspace_response = client.get(f"/api/workspace/{trip_id}")
    _require(
        reloaded_workspace_response.status_code == 200,
        "live TPP workspace reload after reoptimization failed",
        status=reloaded_workspace_response.status_code,
        body=reloaded_workspace_response.text,
        trip_id=trip_id,
        proposal_id=proposal_id,
        route=f"/api/workspace/{trip_id}",
    )
    reloaded_proposal = dict(reloaded_workspace_response.json().get("proposal_state") or {})
    reloaded_follow_up = dict(reloaded_proposal.get("follow_up") or {})
    reloaded_summary = dict(reloaded_proposal.get("summary") or {})
    reloaded_plan = reloaded_follow_up.get("reoptimization_plan")
    reoptimized_source_version = (
        dict(reoptimized_plan.get("source_version") or {})
        if isinstance(reoptimized_plan, Mapping)
        else {}
    )
    reloaded_source_version = (
        dict(reloaded_plan.get("source_version") or {})
        if isinstance(reloaded_plan, Mapping)
        else {}
    )
    _require(
        reloaded_follow_up.get("status") == "reoptimized"
        and isinstance(reoptimized_plan, Mapping)
        and bool(reoptimized_plan)
        and isinstance(reloaded_plan, Mapping)
        and bool(reloaded_plan)
        and bool(reloaded_source_version.get("version_id"))
        and reloaded_source_version.get("version_id")
        == reoptimized_source_version.get("version_id")
        and _normalize_public_reoptimization_plan(reloaded_plan)
        == _normalize_public_reoptimization_plan(reoptimized_plan)
        and reloaded_summary.get("evaluation_result_status") == expected_evaluation_status,
        "live TPP workspace reload did not preserve reoptimization plan and pre-action verdict",
        trip_id=trip_id,
        proposal_id=proposal_id,
        reloaded_follow_up_status=reloaded_follow_up.get("status"),
        reloaded_evaluation_status=reloaded_summary.get("evaluation_result_status"),
        expected_source_version_id=reoptimized_source_version.get("version_id"),
        reloaded_source_version_id=reloaded_source_version.get("version_id"),
        expected_reoptimization_plan=_normalize_public_reoptimization_plan(reoptimized_plan),
        reloaded_reoptimization_plan=_normalize_public_reoptimization_plan(reloaded_plan),
    )
    return reoptimized_state, reoptimized_summary


def _assert_native_live_tpp_transitions(
    *,
    trip_id: str,
    configured_organization_id: str,
    selected_scenario_id: str,
    expected_source_version: Mapping[str, Any],
    expected_evaluation_status: str,
    observed_transitions: list[tuple[str, str]],
    policy_state: Mapping[str, Any],
    submitted_state: Mapping[str, Any],
    readback_state: Mapping[str, Any],
    readback_summary: Mapping[str, Any],
    policy_summary: Mapping[str, Any] | None = None,
    reoptimized_state: Mapping[str, Any] | None = None,
    reoptimized_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    _assert_native_live_tpp_route_order(
        trip_id=trip_id,
        observed_transitions=observed_transitions,
        expected_evaluation_status=expected_evaluation_status,
    )
    policy_id = _assert_native_live_tpp_policy_state(
        trip_id=trip_id,
        configured_organization_id=configured_organization_id,
        policy_state=policy_state,
        policy_summary=policy_summary,
    )
    execution_id = _assert_native_live_tpp_submission_state(
        trip_id=trip_id,
        configured_organization_id=configured_organization_id,
        policy_id=policy_id,
        selected_scenario_id=selected_scenario_id,
        expected_source_version=expected_source_version,
        submitted_state=submitted_state,
    )
    _assert_native_live_tpp_verdict_readback(
        trip_id=trip_id,
        configured_organization_id=configured_organization_id,
        execution_id=execution_id,
        selected_scenario_id=selected_scenario_id,
        expected_source_version=expected_source_version,
        expected_evaluation_status=expected_evaluation_status,
        readback_state=readback_state,
        readback_summary=readback_summary,
    )
    if expected_evaluation_status == "compliant":
        return None
    _require(
        reoptimized_state is not None and reoptimized_summary is not None,
        "live TPP non-compliant journey did not capture persisted reoptimization readback",
        trip_id=trip_id,
    )
    assert reoptimized_state is not None and reoptimized_summary is not None
    evaluation_id = str(
        dict(dict(readback_state.get("evaluation") or {}).get("evaluation_result") or {}).get(
            "evaluation_id"
        )
        or ""
    )
    return _assert_native_live_tpp_reoptimization_readback(
        trip_id=trip_id,
        evaluation_id=evaluation_id,
        expected_source_version=expected_source_version,
        expected_evaluation_status=expected_evaluation_status,
        reoptimized_state=reoptimized_state,
        reoptimized_summary=reoptimized_summary,
    )


@contextmanager
def _record_client_transitions(client: TestClient) -> Iterator[list[tuple[str, str]]]:
    observed_transitions: list[tuple[str, str]] = []
    original_request = client.request

    def _recording_request(method: str, url: str, *args: Any, **kwargs: Any) -> Any:
        path = str(url).split("?", 1)[0]
        observed_transitions.append((method.upper(), path))
        return original_request(method, url, *args, **kwargs)

    client.request = _recording_request  # type: ignore[method-assign,assignment]
    try:
        yield observed_transitions
    finally:
        client.request = original_request  # type: ignore[method-assign]


def _build_compatibility_control(
    *,
    trip_id: str,
    proposal_id: str,
    expected_evaluation_status: str,
    configured_organization_id: str,
    policy_summary: Mapping[str, Any],
    readback_source_version: Mapping[str, Any],
    expected_source_version: Mapping[str, Any],
    offline_control: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if offline_control is not None:
        offline_retained = (
            offline_control.get("trip_id") == trip_id
            and offline_control.get("proposal_id") == proposal_id
            and offline_control.get("evaluation_status") == expected_evaluation_status
        )
        control: dict[str, Any] = {
            "offline_control_scope": "two_app_gate",
            "offline_fixture_journey_retained": offline_retained,
            "offline_business_proposal_id": str(offline_control.get("proposal_id") or ""),
            "offline_business_evaluation_status": str(
                offline_control.get("evaluation_status") or ""
            ),
            "offline_business_follow_up_status": str(offline_control.get("follow_up_status") or ""),
        }
    else:
        control = {
            "offline_control_scope": "standalone",
            "offline_fixture_journey_retained": True,
        }
    control.update(
        {
            "compatible_with_planner_cache": bool(
                policy_summary.get("compatible_with_planner_cache")
            ),
            "contract_version": str(policy_summary.get("contract_version") or ""),
            "organization_id": configured_organization_id,
            "saved_scenario_lineage_preserved": (
                dict(readback_source_version) == dict(expected_source_version)
            ),
        }
    )
    return control


def _run_live_tpp_journey(
    client: TestClient,
    trip_id: str,
    env: dict[str, str],
    *,
    expected_evaluation_status: str = EXPECTED_BUSINESS_EVALUATION_STATUS,
    offline_control: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _evaluation_fixture_name(expected_evaluation_status)

    with _started_tpp_service(env) as (base_url, _process):  # noqa: SIM117
        with _temporary_tpp_client_environment(base_url, env):
            configured_organization_id = os.environ["TPP_ORGANIZATION_ID"]
            with _record_client_transitions(client) as observed_transitions:
                policy_response = client.post(
                    f"/api/workspace/{trip_id}/policy/sync",
                    json={},
                )
                _require(
                    policy_response.status_code == 200,
                    "live TPP policy sync failed",
                    status=policy_response.status_code,
                    body=policy_response.text,
                    trip_id=trip_id,
                    route=f"/api/workspace/{trip_id}/policy/sync",
                )
                policy_payload = policy_response.json()
                policy_state = dict(policy_payload.get("policy_state") or {})
                policy_state_id = str(
                    policy_state.get("policy_state_id") or f"policy-state:{trip_id}"
                )

                # This is synthetic verifier input, entered through the same API as a
                # traveler. Real TPP policy must see complete fare/cabin/expense facts;
                # production must continue to reject missing traveler-supplied facts.
                price_input: dict[str, Any] = {
                    "component": "transport",
                    "amount": 620.0,
                    "lowest_amount": (
                        620.0 if expected_evaluation_status == "compliant" else 400.0
                    ),
                    "currency": "USD",
                    "note": "Synthetic full-product verification fare evidence",
                    "evidence_attested": True,
                    "cabin_class": "economy",
                    "flight_hours": 2.5,
                }
                price_response = client.put(
                    f"/api/workspace/{trip_id}/prices",
                    json=price_input,
                )
                _require(
                    price_response.status_code == 200,
                    "live TPP synthetic fare setup failed",
                    status=price_response.status_code,
                    body=price_response.text,
                    trip_id=trip_id,
                )

                selected_scenario_id, expected_source_version = _ensure_live_saved_scenario_lineage(
                    client,
                    trip_id=trip_id,
                    policy_state_id=policy_state_id,
                )

                submission_response = client.post(
                    f"/api/workspace/{trip_id}/proposal/submit",
                    json={},
                )
                _require(
                    submission_response.status_code == 200,
                    "live TPP proposal submission failed",
                    status=submission_response.status_code,
                    body=submission_response.text,
                    trip_id=trip_id,
                    route=f"/api/workspace/{trip_id}/proposal/submit",
                )
                submission_payload = submission_response.json()
                submitted_state = dict(submission_payload.get("proposal_state") or {})
                proposal_id = str(submitted_state.get("proposal_id") or f"proposal:{trip_id}")
                execution_id = str(submitted_state.get("execution_id") or "")

                status_response = client.post(f"/api/workspace/{trip_id}/proposal/refresh")
                _require(
                    status_response.status_code == 200,
                    "live TPP proposal status poll failed",
                    status=status_response.status_code,
                    body=status_response.text,
                    trip_id=trip_id,
                    proposal_id=proposal_id,
                    execution_id=execution_id,
                )
                status_summary = dict(status_response.json().get("summary") or {})

                readback_response = client.get(f"/api/workspace/{trip_id}/proposal")
                _require(
                    readback_response.status_code == 200,
                    "live TPP persisted proposal readback failed",
                    status=readback_response.status_code,
                    body=readback_response.text,
                    trip_id=trip_id,
                    proposal_id=proposal_id,
                    route=f"/api/workspace/{trip_id}/proposal",
                )
                readback_payload = readback_response.json()
                readback_state = dict(readback_payload.get("proposal_state") or {})
                readback_summary = dict(readback_payload.get("summary") or {})
                reoptimized_state: dict[str, Any] | None = None
                reoptimized_summary: dict[str, Any] | None = None
                if expected_evaluation_status != "compliant":
                    _assert_native_live_tpp_verdict_readback(
                        trip_id=trip_id,
                        configured_organization_id=configured_organization_id,
                        execution_id=execution_id,
                        selected_scenario_id=selected_scenario_id,
                        expected_source_version=expected_source_version,
                        expected_evaluation_status=expected_evaluation_status,
                        readback_state=readback_state,
                        readback_summary=readback_summary,
                    )
                    _require(
                        dict(
                            dict(readback_state.get("evaluation") or {}).get("evaluation_result")
                            or {}
                        ).get("status")
                        == "non_compliant"
                        and readback_summary.get("evaluation_result_status") == "non_compliant",
                        "live TPP reoptimization requires an actual non_compliant verdict readback",
                        trip_id=trip_id,
                        proposal_id=proposal_id,
                        actual_evaluation_status=readback_summary.get("evaluation_result_status"),
                    )
                    reoptimized_state, reoptimized_summary = _execute_live_tpp_reoptimization(
                        client,
                        trip_id=trip_id,
                        proposal_id=proposal_id,
                        expected_evaluation_status=expected_evaluation_status,
                    )

            policy_summary = dict(policy_payload.get("summary") or {})
            reoptimization_plan = _assert_native_live_tpp_transitions(
                trip_id=trip_id,
                configured_organization_id=configured_organization_id,
                selected_scenario_id=selected_scenario_id,
                expected_source_version=expected_source_version,
                expected_evaluation_status=expected_evaluation_status,
                observed_transitions=observed_transitions,
                policy_state=policy_state,
                submitted_state=submitted_state,
                readback_state=readback_state,
                readback_summary=readback_summary,
                policy_summary=policy_summary,
                reoptimized_state=reoptimized_state,
                reoptimized_summary=reoptimized_summary,
            )

            policy_id = str(policy_state["policy_id"])
            policy_version = str(policy_state["policy_version"])
            policy_request_id = str(policy_state["source_request_id"])
            submission_request_id = str(dict(submitted_state.get("submission") or {})["request_id"])
            readback_evaluation = dict(readback_state.get("evaluation") or {})
            readback_evaluation_result = dict(readback_evaluation.get("evaluation_result") or {})
            evaluation_id = str(readback_evaluation_result["evaluation_id"])
            readback_source_version = dict(
                dict(readback_state.get("proposal") or {}).get("source_version") or {}
            )
            final_summary = (
                reoptimized_summary if reoptimized_summary is not None else readback_summary
            )
            native_transitions = {
                "policy_sync": f"POST /api/workspace/{trip_id}/policy/sync",
                "proposal_submit": f"POST /api/workspace/{trip_id}/proposal/submit",
                "proposal_refresh": f"POST /api/workspace/{trip_id}/proposal/refresh",
                "verdict_readback": f"GET /api/workspace/{trip_id}/proposal",
            }
            if expected_evaluation_status != "compliant":
                native_transitions["reoptimize"] = (
                    f"POST /api/workspace/{trip_id}/proposal/reoptimize"
                )
            compatibility_control = _build_compatibility_control(
                trip_id=trip_id,
                proposal_id=proposal_id,
                expected_evaluation_status=expected_evaluation_status,
                configured_organization_id=configured_organization_id,
                policy_summary=policy_summary,
                readback_source_version=readback_source_version,
                expected_source_version=expected_source_version,
                offline_control=offline_control,
            )

            result: dict[str, Any] = {
                "base_url": base_url,
                "trip_id": trip_id,
                "organization_id": configured_organization_id,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "proposal_id": proposal_id,
                "proposal_version": str(readback_state["proposal_version"]),
                "scenario_id": selected_scenario_id,
                "saved_scenario_id": str(expected_source_version["saved_scenario_id"]),
                "source_version_id": str(expected_source_version["version_id"]),
                "source_version": readback_source_version,
                "execution_id": execution_id,
                "evaluation_id": evaluation_id,
                "status_poll": status_summary["submission_status"],
                "submission_outcome": status_summary["submission_outcome"],
                "submission_error": status_summary["submission_error"],
                "evaluation_transport_status": readback_summary["evaluation_transport_status"],
                "evaluation_status": readback_summary["evaluation_result_status"],
                "follow_up_status": final_summary["follow_up_status"],
                "external_ids": {
                    "policy_id": policy_id,
                    "policy_request_id": policy_request_id,
                    "submission_request_id": submission_request_id,
                    "execution_id": execution_id,
                    "evaluation_id": evaluation_id,
                },
                "verdict_readback": {
                    "evaluation_id": evaluation_id,
                    "status": readback_summary["evaluation_result_status"],
                    "follow_up_status": readback_summary["follow_up_status"],
                    "scenario_id": str(readback_state["scenario_id"]),
                    "saved_scenario_id": str(readback_source_version["saved_scenario_id"]),
                    "source_version_id": str(readback_source_version["version_id"]),
                },
                "native_transitions": native_transitions,
                "input": {
                    "trip_id": trip_id,
                    "organization_id": configured_organization_id,
                    "scenario_id": selected_scenario_id,
                    "saved_scenario_id": str(expected_source_version["saved_scenario_id"]),
                    "source_version_id": str(expected_source_version["version_id"]),
                    "expected_evaluation_status": expected_evaluation_status,
                    "price": dict(price_input),
                },
                "observed_output": {
                    "organization_id": str(readback_state["organization_id"]),
                    "policy_id": policy_id,
                    "policy_version": policy_version,
                    "proposal_id": proposal_id,
                    "proposal_version": str(readback_state["proposal_version"]),
                    "execution_id": execution_id,
                    "evaluation_id": evaluation_id,
                    "evaluation_status": final_summary["evaluation_result_status"],
                    "follow_up_status": final_summary["follow_up_status"],
                    "scenario_id": str(readback_state["scenario_id"]),
                    "saved_scenario_id": str(readback_source_version["saved_scenario_id"]),
                    "source_version_id": str(readback_source_version["version_id"]),
                },
                "compatibility_control": compatibility_control,
            }
            if reoptimization_plan is not None:
                plan_source_version = dict(reoptimization_plan.get("source_version") or {})
                result["reoptimization_readback"] = {
                    "evaluation_id": evaluation_id,
                    "evaluation_status": final_summary["evaluation_result_status"],
                    "follow_up_status": final_summary["follow_up_status"],
                    "reaction_kind": str(reoptimization_plan["reaction_kind"]),
                    "target_title": str(reoptimization_plan["target_title"]),
                    "source_version_id": str(plan_source_version["version_id"]),
                }
            return result


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
def _temporary_tpp_client_environment(base_url: str, env: Mapping[str, str]) -> Iterator[None]:
    """Route a planner request to the live TPP process for one verification step."""

    tpp_env = {
        "TPP_BASE_URL": base_url,
        "TPP_ACCESS_TOKEN": env["TPP_ACCESS_TOKEN"],
        "TPP_OIDC_PROVIDER": env["TPP_OIDC_PROVIDER"],
        "TPP_ORGANIZATION_ID": _resolved_tpp_organization_id(env),
    }
    previous = {key: os.environ.get(key) for key in tpp_env}
    os.environ.update(tpp_env)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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


@contextmanager
def _enable_local_fixture_envelopes() -> Iterator[None]:
    """Allow serialized TPP fixtures only for this offline verification harness."""

    managed_keys = ("TRIP_PLANNER_ENV", "TRIP_PLANNER_ALLOW_FIXTURE_TPP_RESPONSES")
    previous = {key: os.environ.get(key) for key in managed_keys}
    os.environ["TRIP_PLANNER_ENV"] = "local"
    os.environ["TRIP_PLANNER_ALLOW_FIXTURE_TPP_RESPONSES"] = "true"
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_product_journeys(
    *,
    live_tpp: str,
    expected_business_evaluation_status: str = EXPECTED_BUSINESS_EVALUATION_STATUS,
) -> list[CheckResult]:
    planner_llm_env = dict(os.environ)
    with (
        tempfile.TemporaryDirectory(prefix="trip-planner-full-product.") as tmpdir,
        _temporary_database_url(f"sqlite:///{Path(tmpdir) / 'full_product.db'}"),
        _force_planner_fallback_runtime(),
        _enable_local_fixture_envelopes(),
    ):
        reset_database_state()
        ensure_database_ready()
        app = create_app()
        results: list[CheckResult] = []
        tpp_status = tpp_prerequisite_status(live_tpp=live_tpp)

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
                        "planning_mode": leisure_payload["session"]["selected_planning_mode"],
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

            if tpp_status.status == "READY":
                live_tpp_env = {key: str(value) for key, value in tpp_status.details.items()}
                with (
                    _started_tpp_service(live_tpp_env) as (base_url, _process),
                    _temporary_tpp_client_environment(base_url, live_tpp_env),
                ):
                    refresh = client.post(f"/api/workspace/{business_trip_id}/proposal/refresh")
            else:
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
                in {"deferred", "failed", "retry_scheduled", "succeeded"},
                "local proposal status poll did not preserve a recognizable state",
                trip_id=business_trip_id,
                proposal_id=proposal["proposal_id"],
                summary=refresh_payload["summary"],
            )
            evaluation_fixture_name = _evaluation_fixture_name(expected_business_evaluation_status)
            evaluation_request = _prepared_evaluation_request(
                business_trip_id,
                proposal["proposal_id"],
                execution_id,
                fixture_name=evaluation_fixture_name,
            )
            evaluation_response = _prepared_evaluation_response(
                business_trip_id,
                proposal["proposal_id"],
                execution_id,
                fixture_name=evaluation_fixture_name,
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
            expected_approval_ready = expected_business_evaluation_status == "compliant"
            _require(
                evaluation_payload["summary"]["approval_ready"] is expected_approval_ready,
                "business evaluation approval state did not match the expected outcome",
                trip_id=business_trip_id,
                proposal_id=proposal["proposal_id"],
                expected_evaluation_status=expected_business_evaluation_status,
                approval_ready=evaluation_payload["summary"]["approval_ready"],
            )
            reloaded_business_workspace = client.get(f"/api/workspace/{business_trip_id}")
            _require(
                reloaded_business_workspace.status_code == 200,
                "business workspace reload after evaluation failed",
                status=reloaded_business_workspace.status_code,
                trip_id=business_trip_id,
            )
            reloaded_proposal = reloaded_business_workspace.json()["proposal_state"]
            expected_follow_up_status = (
                "resolved"
                if expected_business_evaluation_status == "compliant"
                else "no_scenario_lineage"
            )
            _require(
                reloaded_proposal["summary"]["follow_up_status"] == expected_follow_up_status,
                "business workspace follow-up state did not match the expected outcome",
                trip_id=business_trip_id,
                proposal_id=proposal["proposal_id"],
                expected_evaluation_status=expected_business_evaluation_status,
                expected_follow_up_status=expected_follow_up_status,
                follow_up=reloaded_proposal["summary"].get("follow_up"),
            )
            local_business_details = {
                "trip_id": business_trip_id,
                "proposal_id": proposal["proposal_id"],
                "evaluation_status": evaluation_payload["summary"]["evaluation_result_status"],
                "planning_mode": reloaded_business_workspace.json()["session"][
                    "selected_planning_mode"
                ],
                "follow_up_status": evaluation_payload["summary"]["follow_up_status"],
                "status_poll": refresh_payload["summary"]["submission_status"],
            }
            _assert_business_verification_outcomes(
                local_business_details,
                expected_evaluation_status=expected_business_evaluation_status,
                require_status_poll=live_tpp != "off",
            )
            results.append(CheckResult("local-business-journey", "PASS", local_business_details))

            map_result = classify_map_prerequisite()
            results.append(map_result)
            if map_result.status == "FAIL":
                raise VerificationFailure(json.dumps(map_result.details, sort_keys=True))

            results.append(classify_planner_llm_prerequisite(env=planner_llm_env))

            if tpp_status.status == "READY":
                live_details = _run_live_tpp_journey(
                    client,
                    business_trip_id,
                    {key: str(value) for key, value in tpp_status.details.items()},
                    expected_evaluation_status=expected_business_evaluation_status,
                    offline_control=local_business_details,
                )
                _assert_business_verification_outcomes(
                    local_business_details,
                    expected_evaluation_status=expected_business_evaluation_status,
                    live_details=live_details,
                )
                results.append(CheckResult("live-tpp", "PASS", live_details))
            else:
                results.append(tpp_status)
                if live_tpp == "required":
                    raise VerificationFailure(json.dumps(tpp_status.details, sort_keys=True))

        return results


# These are product observations, not a replacement for the strict journey gate.
CONTRACT_VERDICTS = ("WORKS", "PARTIAL", "BROKEN", "FABRICATED")


def _observe(
    client: TestClient, evidence: dict[str, Any], method: str, path: str, **kwargs: Any
) -> dict[str, Any]:
    response = client.request(method, path, **kwargs)
    try:
        body = response.json()
    except ValueError:
        body = {"text": response.text}
    evidence.setdefault("requests", []).append(
        {"method": method, "path": path, "status": response.status_code, "body": body}
    )
    _require(
        200 <= response.status_code < 300,
        "contract route failed",
        status=response.status_code,
        path=path,
    )
    return body


def _probe_identity(client: TestClient, evidence: dict[str, Any]) -> str:
    user_id = _signup(client)
    evidence["signup_user_id"] = user_id
    session = _observe(client, evidence, "GET", "/api/auth/session")
    email = session["user"]["email"]
    _observe(client, evidence, "POST", "/api/auth/logout")
    login = _observe(
        client,
        evidence,
        "POST",
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    _observe(client, evidence, "GET", "/api/trips")
    persisted = _observe(client, evidence, "GET", "/api/auth/session")
    return (
        "WORKS"
        if login["user"]["user_id"] == persisted["user"]["user_id"] == user_id
        else "PARTIAL"
    )


def _probe_trips(client: TestClient, evidence: dict[str, Any]) -> str:
    complete = []
    for region, count, days in (("Chicago", 1, 1), ("Reykjavik, Iceland", 8, 14)):
        title = f"Contract business purpose {region}"
        trip_id = _create_trip(
            client,
            mode="business",
            title=title,
            region=region,
            traveler_count=count,
            duration_days=days,
        )
        trip = _observe(client, evidence, "GET", f"/api/trips/{trip_id}")["trip"]
        frame = trip["trip_frame"]
        complete.append(
            trip["title"] == title
            and trip["mode"] == "business"
            and frame["primary_regions"] == [region]
            and frame["traveler_party"]["traveler_count"] == count
            and frame["duration_days"] == days
            and frame["start_date"] == (date.today() + timedelta(days=45)).isoformat()
            and frame["end_date"] == (date.today() + timedelta(days=44 + days)).isoformat()
        )
    return "WORKS" if all(complete) else "PARTIAL"


def _comparison_figures(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            key: row.get("metrics", {}).get(key)
            for key in ("estimated_total", "travel_minutes", "transfers")
        }
        for row in sorted(payload.get("scenarios", []), key=lambda row: row["rank"])
    ]


def _comparison_policy_previews(payload: dict[str, Any]) -> list[Any]:
    return [
        row.get("policy_preview")
        for row in sorted(payload.get("scenarios", []), key=lambda row: row["rank"])
    ]


def _comparison_pair(
    client: TestClient,
    evidence: dict[str, Any],
    inputs: tuple[tuple[str, int, float | None], tuple[str, int, float | None]],
) -> list[dict[str, Any]]:
    observations = []
    for region, count, amount in inputs:
        trip_id = _create_trip(
            client,
            mode="business",
            title="Contract comparison",
            region=region,
            traveler_count=count,
        )
        observation: dict[str, Any] = {"destination": region, "party": count}
        if amount is None:
            payload = _observe(
                client, evidence, "GET", f"/api/workspace/{trip_id}/scenarios/compare"
            )
        else:
            observation["requested_total"] = amount
            price_path = f"/api/workspace/{trip_id}/prices"
            _observe(
                client,
                evidence,
                "PUT",
                price_path,
                json={"component": "transport", "amount": amount, "currency": "USD"},
            )
            total = _observe(client, evidence, "GET", price_path)["total"]
            observation["entered_total"] = total["typical_amount"] if total else None
            # The Compare tab reads route_comparison from the workspace, which applies
            # entered prices to the scenario figures.
            workspace = _observe(client, evidence, "GET", f"/api/workspace/{trip_id}")
            payload = workspace["route_comparison"]
            compare = _observe(
                client, evidence, "GET", f"/api/workspace/{trip_id}/scenarios/compare"
            )
            workspace_figures = _comparison_figures(payload)
            compare_figures = _comparison_figures(compare)
            _require(
                compare_figures == workspace_figures
                and _comparison_policy_previews(compare) == _comparison_policy_previews(payload),
                "scenario comparison endpoint did not match workspace route_comparison",
                trip_id=trip_id,
                workspace_figures=workspace_figures,
                compare_figures=compare_figures,
            )
        observation["figures"] = _comparison_figures(payload)
        observations.append(observation)
    return observations


def _probe_comparison(client: TestClient, evidence: dict[str, Any]) -> str:
    pairs = {}
    for determinant, inputs in (
        ("destination", (("Chicago", 1, None), ("Reykjavik, Iceland", 1, None))),
        ("price", (("Chicago", 1, 250.0), ("Chicago", 1, 700.0))),
    ):
        pairs[determinant] = _comparison_pair(client, evidence, inputs)
    evidence["pairs"] = pairs
    controls = evidence["controls"] = {}
    try:
        controls["party"] = _comparison_pair(
            client, evidence, (("Chicago", 1, None), ("Chicago", 8, None))
        )
    except (
        VerificationFailure,
        HTTPError,
        AttributeError,
        LookupError,
        TypeError,
        ValueError,
    ) as exc:
        # This optional control cannot override the measured determinant verdict,
        # including when its response is malformed or its transport is interrupted.
        controls["party_error"] = str(exc)

    if any(not observation["figures"] for pair in pairs.values() for observation in pair):
        return "PARTIAL"
    moved = []
    for determinant, pair in pairs.items():
        if determinant == "price":
            moved.append(
                pair[0]["entered_total"] != pair[1]["entered_total"]
                and all(
                    observation["entered_total"] is not None
                    and observation["entered_total"] == observation["requested_total"]
                    and {
                        (figure["estimated_total"] or {}).get("typical_amount")
                        for figure in observation["figures"]
                    }
                    == {observation["entered_total"]}
                    for observation in pair
                )
            )
        else:
            moved.append(pair[0]["figures"] != pair[1]["figures"])
    # Cross-pair comparison is essential: HTTP success cannot detect fabricated figures.
    if not any(moved):
        return "FABRICATED"
    return "WORKS" if all(moved) else "PARTIAL"


def _probe_planner(client: TestClient, evidence: dict[str, Any]) -> str:
    replies = []
    runtimes = []
    for message in ("Cancel my trip. I no longer want to travel.", "zxqv 923 glorb?!"):
        trip_id = _create_trip(client, mode="business", title="Contract planner", region="Chicago")
        payload = _observe(
            client,
            evidence,
            "POST",
            f"/api/planner/{trip_id}/turns",
            json={"message": message},
        )
        reply = next(
            item["content"]
            for item in reversed(payload["messages"])
            if item["role"] in {"assistant", "planner"}
        )
        replies.append(reply)
        runtimes.append(payload.get("runtime", {}))
    evidence["replies"] = replies
    evidence["reply_sha256"] = [hashlib.sha256(reply.encode()).hexdigest() for reply in replies]
    evidence["runtimes"] = runtimes
    if not all(replies):
        return "PARTIAL"
    if replies[0].encode() == replies[1].encode():
        return "FABRICATED"
    if any(runtime.get("mode") == "fallback" for runtime in runtimes):
        return "PARTIAL"
    # Cancellation language in a refusal does not acknowledge the request.
    if re.search(
        r"\b(?:cannot|can['’]t|unable to|won['’]t|will not|refuse to)\b"
        r"(?:(?!\b(?:but|however|yet)\b)[^,;.!?\n])*\bcancel\w*",
        replies[0],
        re.IGNORECASE,
    ):
        return "PARTIAL"
    # An echoed user message is not an acknowledgement of cancellation.
    acknowledged = re.search(
        r"(?:cancel(?:led|ed|l?ing)|won.t (?:book|plan)|stop(?:ped)? planning)",
        replies[0],
        re.IGNORECASE,
    )
    return "WORKS" if acknowledged else "PARTIAL"


def _import_probe_policy(
    client: TestClient,
    evidence: dict[str, Any],
    trip_id: str,
    *,
    restrictive: bool = False,
) -> dict[str, Any]:
    response = copy.deepcopy(_fixture("policy", "standard_policy_sync.json")["response"])
    rules = response["result_payload"]["constraint_set"]
    if restrictive:
        rules["airfare_rules"]["max_cabin"] = "economy"
        rules["lodging_rules"]["max_nightly_rate_usd"] = 125
    return _observe(
        client,
        evidence,
        "PUT",
        f"/api/workspace/{trip_id}/policy",
        json={
            "request": _prepared_policy_request(trip_id),
            "response": response,
            "source_kind": "tpp_sync",
            "tags": ["contract-probe-local"],
        },
    )


def _probe_policy(client: TestClient, evidence: dict[str, Any]) -> str:
    complete = []
    for restrictive in (False, True):
        trip_id = _create_trip(client, mode="business", title="Contract policy", region="Chicago")
        payload = _import_probe_policy(client, evidence, trip_id, restrictive=restrictive)
        state = payload.get("policy_state") or {}
        constraints = state.get("constraint_set") or {}
        complete.append(
            bool(constraints.get("policy_id"))
            and state.get("sync_status") == "current"
            and constraints.get("airfare_rules", {}).get("max_cabin")
            == ("economy" if restrictive else "premium_economy")
            and constraints.get("lodging_rules", {}).get("max_nightly_rate_usd")
            == (125 if restrictive else 325)
        )
    return "WORKS" if all(complete) else "PARTIAL"


def _submit_probe_proposal(
    client: TestClient, evidence: dict[str, Any], *, airport: str
) -> tuple[str, dict[str, Any]]:
    trip_id = _create_trip(client, mode="business", title="Contract approval", region="Chicago")
    _import_probe_policy(client, evidence, trip_id, restrictive=airport == "KEF")
    proposal = _proposal_payload(trip_id)
    proposal["traveler_context"]["home_airport"] = airport
    payload = _observe(
        client,
        evidence,
        "PUT",
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": proposal,
            "request": _prepared_submission_request(trip_id, proposal["proposal_id"]),
            "response": _fixture("proposal_submit_deferred.json")["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    return trip_id, payload


def _probe_proposal(client: TestClient, evidence: dict[str, Any]) -> str:
    complete = []
    for airport in ("ORD", "KEF"):
        _, payload = _submit_probe_proposal(client, evidence, airport=airport)
        state = payload.get("proposal_state") or {}
        complete.append(bool(state.get("execution_id")))
    return "WORKS" if all(complete) else "PARTIAL"


def _probe_packet(client: TestClient, evidence: dict[str, Any]) -> str:
    trip_id, payload = _submit_probe_proposal(client, evidence, airport="ORD")
    proposal_id = _proposal_payload(trip_id)["proposal_id"]
    execution_id = payload["proposal_state"]["execution_id"]
    _observe(
        client,
        evidence,
        "PUT",
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": _prepared_evaluation_request(trip_id, proposal_id, execution_id),
            "response": _prepared_evaluation_response(trip_id, proposal_id, execution_id),
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    workspace = _observe(client, evidence, "GET", f"/api/workspace/{trip_id}")
    evidence["packet_state"] = workspace.get("proposal_state")
    evidence["print_export_observation"] = (
        "Not exercised: ApprovalPacket is a browser component, not an HTTP packet route. "
        "This offline TestClient probe observes persisted packet inputs only."
    )
    # Do not promote backend readiness into proof that a browser printed/exported a document.
    return "PARTIAL" if workspace.get("proposal_state") else "BROKEN"


def run_contract_report() -> list[dict[str, Any]]:
    rows = []
    probes = (
        _probe_identity,
        _probe_trips,
        _probe_comparison,
        _probe_planner,
        _probe_policy,
        _probe_proposal,
        _probe_packet,
    )
    with (
        tempfile.TemporaryDirectory(prefix="trip-planner-contract.") as tmpdir,
        _temporary_database_url(f"sqlite:///{Path(tmpdir) / 'contract.db'}"),
        _force_planner_fallback_runtime(),
        _enable_local_fixture_envelopes(),
    ):
        reset_database_state()
        ensure_database_ready()
        with TestClient(create_app()) as client:
            for index, probe in enumerate(probes, 1):
                evidence: dict[str, Any] = {"transport": "TestClient; local TPP fixture envelopes"}
                try:
                    verdict = probe(client, evidence)
                except Exception as exc:  # noqa: BLE001 - each probe must report independently.
                    verdict = "BROKEN"
                    evidence["exception"] = {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                rows.append({"id": f"TP{index}", "verdict": verdict, "evidence": evidence})
    return rows


def contract_headline(rows: list[dict[str, Any]]) -> str:
    counts = ", ".join(
        f"{word} {sum(row['verdict'] == word for row in rows)}" for word in CONTRACT_VERDICTS
    )
    return f"product-probe: {counts} of {len(rows)}"


def _print_results(results: list[CheckResult]) -> None:
    print("Full-product verification results")
    for result in results:
        remediation = ""
        if isinstance(result.details, Mapping):
            hint = result.details.get("remediation")
            if isinstance(hint, str) and hint:
                remediation = f"\n    remediation: {hint}"
        print(
            f"- {result.status} {result.name}: "
            f"{json.dumps(result.details, sort_keys=True)}{remediation}"
        )
    for result in results:
        if result.status == "SKIPPED":
            print(f"- WARNING uncovered surface: {result.name}")


# Section 15 receipt capture for the strict gate. The claimed layer depends only on
# these checks; optional providers stay visible as observations outside the claim.
FULL_PRODUCT_RESULT_ENV = "FULL_PRODUCT_RESULT_JSON"
FULL_PRODUCT_REQUIRED_CHECKS = (
    "frontend-runtime-smoke",
    "local-leisure-journey",
    "local-business-journey",
    "live-tpp",
)
FULL_PRODUCT_OPTIONAL_CHECKS = ("map-provider", "planner-llm")
_SECRET_ENV_NAME = re.compile(r"TOKEN|SECRET|PASSWORD|API_KEY|CREDENTIAL", re.IGNORECASE)


def _redacted_failure(exc: BaseException, env: Mapping[str, str]) -> str:
    message = f"{type(exc).__name__}: {exc}"
    for name, value in env.items():
        if _SECRET_ENV_NAME.search(name) and len(value.strip()) >= 4:
            message = message.replace(value.strip(), "[redacted]")
    return message[:400]


def full_product_result(
    *,
    command: str,
    exit_code: int,
    results: list[CheckResult] | None,
    failure: BaseException | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Summarise a strict run by check name and status only; details stay in the log."""
    by_name = {result.name: result.status for result in results or []}
    required = [
        {"name": name, "status": by_name.get(name, "MISSING")}
        for name in FULL_PRODUCT_REQUIRED_CHECKS
    ]
    required_skipped = sum(check["status"] in {"SKIPPED", "BLOCKED"} for check in required)
    if exit_code != 0 or failure is not None:
        status = "FAIL"
    elif required_skipped:
        status = "SKIPPED"
    elif any(check["status"] != "PASS" for check in required):
        status = "INCOMPLETE"
    else:
        status = "PASS"
    payload: dict[str, Any] = {
        "layer": "configured_full_product",
        "command": command,
        "exit_code": exit_code,
        "status": status,
        "required_checks": required,
        "required_skipped": required_skipped,
        "optional_observations": [
            {"name": name, "status": by_name[name]}
            for name in FULL_PRODUCT_OPTIONAL_CHECKS
            if name in by_name
        ],
    }
    if failure is not None:
        payload["failure"] = _redacted_failure(failure, os.environ if env is None else env)
    return payload


def _write_full_product_result(payload: dict[str, Any]) -> None:
    destination = os.environ.get(FULL_PRODUCT_RESULT_ENV, "").strip()
    if not destination:
        return
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    command = shlex.join(["python", "scripts/check_full_product_verification.py", *argv])
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
    parser.add_argument(
        "--contract-report",
        type=Path,
        help="Write seven product observations; negative verdicts exit zero.",
    )
    args = parser.parse_args(argv)
    if args.contract_report is not None:
        # Keep the existing strict gate behavior outside report mode. A journey failure
        # must never prevent the independent contract observations from being collected.
        try:
            _print_results(run_product_journeys(live_tpp=args.live_tpp))
        except Exception as exc:  # noqa: BLE001 - report mode preserves contract observations.
            print(
                f"Existing product journey failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        rows = run_contract_report()
        args.contract_report.parent.mkdir(parents=True, exist_ok=True)
        args.contract_report.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(contract_headline(rows))
        return 0
    results: list[CheckResult] = []
    try:
        if not args.skip_frontend_smoke:
            results.append(run_frontend_runtime_smoke())
        results.extend(run_product_journeys(live_tpp=args.live_tpp))
    except VerificationFailure as exc:
        print(f"Full-product verification failed: {exc}", file=sys.stderr)
        _write_full_product_result(
            full_product_result(command=command, exit_code=1, results=results, failure=exc)
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI boundary reports unexpected failures.
        print(
            "Full-product verification failed due to an unexpected error: "
            f"{type(exc).__name__}: {exc}. Check repository/configuration paths "
            "and local service setup, including TPP_REPO_PATH and subprocess working directories.",
            file=sys.stderr,
        )
        _write_full_product_result(
            full_product_result(command=command, exit_code=1, results=results, failure=exc)
        )
        return 1
    _print_results(results)
    _write_full_product_result(full_product_result(command=command, exit_code=0, results=results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
