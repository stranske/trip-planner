"""Client interfaces for Travel-Plan-Permission execution workflows."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol
import json
from urllib import error as urllib_error
from urllib import request as urllib_request

from .contracts import TPPRequestEnvelope, TPPResponseEnvelope


class TPPIntegrationClient(Protocol):
    """Transport-neutral operations for the Travel-Plan-Permission boundary."""

    def fetch_policy_constraints(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope: ...

    def submit_proposal(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope: ...

    def fetch_evaluation_result(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope: ...

    def poll_execution_status(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope: ...


class BaseTPPIntegrationClient(ABC):
    """Validates operation routing while leaving transport details to subclasses."""

    def fetch_policy_constraints(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self._dispatch("fetch_policy_constraints", request)

    def submit_proposal(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self._dispatch("submit_proposal", request)

    def fetch_evaluation_result(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self._dispatch("fetch_evaluation_result", request)

    def poll_execution_status(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        return self._dispatch("poll_execution_status", request)

    def _dispatch(
        self, expected_operation: str, request: TPPRequestEnvelope
    ) -> TPPResponseEnvelope:
        if request.operation != expected_operation:
            raise ValueError(
                f"request.operation must be {expected_operation!r}, got {request.operation!r}"
            )
        return self.execute(request)

    @abstractmethod
    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        """Execute a validated TPP request through the concrete transport."""


class TPPTransportError(RuntimeError):
    """Raised when a live TPP transport call cannot be completed safely."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class TPPConfigurationError(TPPTransportError):
    """Raised when live TPP transport is requested without runtime config."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class TPPContractError(TPPTransportError):
    """Raised when the upstream TPP service returns an invalid contract."""


class TPPServiceUnavailableError(TPPTransportError):
    """Raised when the upstream TPP service cannot be reached."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


def _strip_none_values(value: Any) -> Any:
    """Drop null fields before serializing live TPP request payloads."""

    if isinstance(value, dict):
        return {
            key: _strip_none_values(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_strip_none_values(item) for item in value if item is not None]
    return value


@dataclass(slots=True)
class TPPRuntimeSettings:
    base_url: str
    access_token: str
    oidc_provider: str
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "TPPRuntimeSettings":
        base_url = os.getenv("TPP_BASE_URL", "").strip()
        access_token = os.getenv("TPP_ACCESS_TOKEN", "").strip()
        oidc_provider = os.getenv("TPP_OIDC_PROVIDER", "").strip()
        timeout_raw = os.getenv("TPP_TIMEOUT_SECONDS", "").strip()

        missing = [
            name
            for name, value in (
                ("TPP_BASE_URL", base_url),
                ("TPP_ACCESS_TOKEN", access_token),
                ("TPP_OIDC_PROVIDER", oidc_provider),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise TPPConfigurationError(
                f"Live TPP transport requires runtime configuration for {joined}."
            )

        timeout_seconds = 10.0
        if timeout_raw:
            try:
                timeout_seconds = float(timeout_raw)
            except ValueError as exc:
                raise TPPConfigurationError(
                    "TPP_TIMEOUT_SECONDS must be a numeric value when provided."
                ) from exc
            if timeout_seconds <= 0:
                raise TPPConfigurationError("TPP_TIMEOUT_SECONDS must be greater than 0.")

        return cls(
            base_url=base_url.rstrip("/"),
            access_token=access_token,
            oidc_provider=oidc_provider,
            timeout_seconds=timeout_seconds,
        )


class HTTPTPPIntegrationClient(BaseTPPIntegrationClient):
    """Executes TPP operations over the planner-facing HTTP seam."""

    def __init__(self, settings: TPPRuntimeSettings | None = None) -> None:
        self.settings = settings or TPPRuntimeSettings.from_env()

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        if request.operation == "fetch_policy_constraints":
            return self._fetch_policy_constraints(request)
        if request.operation == "submit_proposal":
            return self._submit_proposal(request)
        if request.operation == "fetch_evaluation_result":
            return self._fetch_evaluation_result(request)
        if request.operation == "poll_execution_status":
            return self._poll_execution_status(request)
        raise TPPContractError(f"Unsupported TPP operation {request.operation!r}.")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-TPP-OIDC-Provider": self.settings.oidc_provider,
        }

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        json_payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.settings.base_url}{path}"
        body = json.dumps(json_payload).encode("utf-8")
        request = urllib_request.Request(
            url,
            data=body,
            headers=self._headers(),
            method=method,
        )
        try:
            with urllib_request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                status_code = response.status
                raw_body = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            body_excerpt = raw_body.strip()
            if len(body_excerpt) > 280:
                body_excerpt = f"{body_excerpt[:277]}..."
            raise TPPTransportError(
                f"TPP request to {path} returned HTTP {exc.code}: {body_excerpt or 'no response body'}",
                status_code=502,
            ) from exc
        except urllib_error.URLError as exc:
            raise TPPServiceUnavailableError(
                f"TPP request to {path} failed: {exc}."
            ) from exc

        if status_code >= 400:
            body_excerpt = raw_body.strip()
            if len(body_excerpt) > 280:
                body_excerpt = f"{body_excerpt[:277]}..."
            raise TPPTransportError(
                f"TPP request to {path} returned HTTP {status_code}: {body_excerpt or 'no response body'}",
                status_code=502,
            )

        try:
            payload = json.loads(raw_body)
        except ValueError:
            raise TPPContractError(
                f"TPP request to {path} returned a non-JSON response."
            )
        if not isinstance(payload, dict):
            raise TPPContractError(
                f"TPP request to {path} returned a non-object JSON payload."
            )
        return payload

    def _policy_request_payload(self, request: TPPRequestEnvelope) -> dict[str, Any]:
        payload = dict(request.payload)
        payload.setdefault("trip_id", request.trip_id)
        if request.submitted_at is not None:
            payload.setdefault("requested_at", request.submitted_at)
        if payload.get("trip_id") in (None, ""):
            raise TPPContractError(
                "Live policy sync requires request.trip_id or payload.trip_id."
            )
        return _strip_none_values(payload)

    def _proposal_request_payload(self, request: TPPRequestEnvelope) -> dict[str, Any]:
        payload = dict(request.payload)
        payload.setdefault("trip_id", request.trip_id)
        payload.setdefault("proposal_id", request.proposal_id)
        payload.setdefault("proposal_version", payload.get("proposal_version"))
        payload.setdefault("request_id", request.request_id)
        payload.setdefault("correlation_id", request.correlation_id.to_dict())
        payload.setdefault("transport_pattern", request.transport_pattern)
        payload.setdefault("organization_id", request.organization_id)
        if request.submitted_at is not None:
            payload.setdefault("submitted_at", request.submitted_at)
        if (
            payload.get("trip_id") in (None, "")
            or payload.get("proposal_id") in (None, "")
            or payload.get("proposal_version") in (None, "")
        ):
            raise TPPContractError(
                "Live proposal submission requires trip_id, proposal_id, and proposal_version."
            )
        return _strip_none_values(payload)

    def _status_request_payload(self, request: TPPRequestEnvelope) -> dict[str, Any]:
        payload = dict(request.payload)
        payload.setdefault("trip_id", request.trip_id)
        payload.setdefault("proposal_id", request.proposal_id)
        payload.setdefault("proposal_version", payload.get("proposal_version"))
        payload.setdefault("execution_id", payload.get("execution_id"))
        payload.setdefault("request_id", request.request_id)
        if request.submitted_at is not None:
            payload.setdefault("requested_at", request.submitted_at)
        if payload.get("trip_id") in (None, "") or payload.get("proposal_id") in (None, ""):
            raise TPPContractError(
                "Live TPP status operations require trip_id and proposal_id."
            )
        if payload.get("proposal_version") in (None, ""):
            raise TPPContractError(
                "Live TPP status operations require payload.proposal_version."
            )
        if payload.get("execution_id") in (None, ""):
            raise TPPContractError(
                "Live TPP status operations require payload.execution_id."
            )
        return _strip_none_values(payload)

    def _adapt_execution_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        execution = payload.get("execution_status")
        if execution is None:
            submission_status = str(payload.get("submission_status") or "").strip().lower()
            if submission_status in {"approved", "compliant", "succeeded"}:
                state = "succeeded"
                terminal = True
            elif submission_status in {"rejected", "failed", "non_compliant"}:
                state = "failed"
                terminal = True
            elif submission_status in {"submitted", "queued"}:
                state = "accepted"
                terminal = False
            else:
                state = "running"
                terminal = False
            return {
                "state": state,
                "terminal": terminal,
                "summary": str(payload.get("submission_status") or "").replace("_", " "),
                "external_status": "",
                "updated_at": payload.get("received_at"),
            }
        if not isinstance(execution, dict):
            raise TPPContractError("TPP execution_status must be an object when provided.")
        return {
            "state": execution.get("state"),
            "terminal": execution.get("terminal"),
            "summary": execution.get("summary", ""),
            "external_status": execution.get("external_status", ""),
            "poll_after_seconds": execution.get("poll_after_seconds"),
            "updated_at": execution.get("updated_at"),
        }

    def _adapt_error(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        error = payload.get("error")
        if error is None:
            return None
        if not isinstance(error, dict):
            raise TPPContractError("TPP error must be an object when provided.")
        return {
            "code": str(error.get("code") or "tpp_error"),
            "message": str(error.get("message") or "TPP returned an error."),
            "category": str(error.get("category") or "transport"),
            "retryable": bool(error.get("retryable", False)),
            "details": {
                key: str(value)
                for key, value in error.items()
                if key not in {"code", "message", "category", "retryable"} and value is not None
            },
        }

    def _adapt_retry(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        retry = payload.get("retry")
        if retry is None:
            return None
        if not isinstance(retry, dict):
            raise TPPContractError("TPP retry metadata must be an object when provided.")
        return {
            "attempt": int(retry.get("attempt", 0)),
            "max_attempts": int(retry.get("max_attempts", 1)),
            "retryable": bool(retry.get("retryable", False)),
            "backoff_seconds": retry.get("backoff_seconds"),
            "next_retry_at": retry.get("next_retry_at"),
            "reason": str(retry.get("reason") or ""),
        }

    def _fetch_policy_constraints(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        payload = self._request_json(
            method="GET",
            path="/api/planner/policy-snapshot",
            json_payload=self._policy_request_payload(request),
        )
        versioning = payload.get("versioning")
        if not isinstance(versioning, dict):
            raise TPPContractError(
                "TPP policy snapshot response is missing versioning metadata."
            )

        policy_version = str(versioning.get("policy_version") or "").strip()
        if not policy_version:
            raise TPPContractError("TPP policy snapshot response is missing policy_version.")

        organization_context = request.payload.get("organization_context")
        organization_context_dict = (
            organization_context if isinstance(organization_context, dict) else {}
        )
        organization_id = (
            request.organization_id
            or str(organization_context_dict.get("organization_id") or "").strip()
            or "tpp"
        )
        documentation_rules = [
            str(item.get("code") or item.get("summary") or "").strip()
            for item in payload.get("documentation_rules") or []
            if isinstance(item, dict) and str(item.get("code") or item.get("summary") or "").strip()
        ]
        approval_triggers = [
            str(item.get("code") or item.get("summary") or "").strip()
            for item in payload.get("approval_triggers") or []
            if isinstance(item, dict) and str(item.get("code") or item.get("summary") or "").strip()
        ]
        freshness = str(payload.get("freshness") or "current").strip() or "current"
        result_payload = {
            "constraint_set": {
                "policy_id": str(versioning.get("etag") or f"{organization_id}:{policy_version}"),
                "organization_id": organization_id,
                "policy_version": policy_version,
                "required_booking_channels": [],
                "airfare_rules": {},
                "lodging_rules": {},
                "ground_transport_rules": {},
                "meal_rules": {},
                "approval_rules": approval_triggers,
                "documentation_rules": documentation_rules,
                "allowed_exception_types": [],
            },
            "organization_context": {
                "organization_id": organization_id,
                "approved_channels": [],
                "comparable_requirements": {},
                "documentation_rules": documentation_rules,
                "approval_triggers": approval_triggers,
                "comfort_preferences": {},
                "class_of_service_limits": {},
                "metadata": {
                    "policy_status": str(payload.get("policy_status") or ""),
                    "contract_version": str(versioning.get("contract_version") or ""),
                    "etag": str(versioning.get("etag") or ""),
                },
            },
            "freshness": {
                "snapshot_version": str(versioning.get("etag") or policy_version),
                "captured_at": payload.get("generated_at"),
                "fresh_until": payload.get("expires_at"),
                "invalidated_at": payload.get("invalidated_at"),
                "invalidation_reason": payload.get("invalidation_reason"),
                "status": freshness,
            },
        }
        return TPPResponseEnvelope.from_dict(
            {
                "operation": request.operation,
                "request_id": request.request_id,
                "correlation_id": request.correlation_id.to_dict(),
                "transport_pattern": request.transport_pattern,
                "execution_status": {
                    "state": "succeeded",
                    "terminal": True,
                    "summary": "Policy snapshot fetched from TPP.",
                    "external_status": "200 OK",
                    "updated_at": payload.get("generated_at"),
                },
                "result_payload": result_payload,
                "received_at": payload.get("generated_at"),
            }
        )

    def _submit_proposal(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        payload = self._request_json(
            method="POST",
            path="/api/planner/proposals",
            json_payload=self._proposal_request_payload(request),
        )
        return TPPResponseEnvelope.from_dict(
            {
                "operation": request.operation,
                "request_id": request.request_id,
                "correlation_id": request.correlation_id.to_dict(),
                "transport_pattern": payload.get("transport_pattern", request.transport_pattern),
                "execution_status": self._adapt_execution_status(payload),
                "result_payload": payload.get("result_payload") or {},
                "error": self._adapt_error(payload),
                "retry": self._adapt_retry(payload),
                "received_at": payload.get("received_at"),
                "status_endpoint": payload.get("status_endpoint"),
            }
        )

    def _poll_execution_status(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        status_request = self._status_request_payload(request)
        payload = self._request_json(
            method="GET",
            path=(
                f"/api/planner/proposals/{status_request['proposal_id']}"
                f"/executions/{status_request['execution_id']}"
            ),
            json_payload=status_request,
        )
        return TPPResponseEnvelope.from_dict(
            {
                "operation": request.operation,
                "request_id": request.request_id,
                "correlation_id": request.correlation_id.to_dict(),
                "transport_pattern": payload.get("transport_pattern", request.transport_pattern),
                "execution_status": self._adapt_execution_status(payload),
                "result_payload": payload.get("result_payload") or {},
                "error": self._adapt_error(payload),
                "retry": self._adapt_retry(payload),
                "received_at": payload.get("received_at"),
                "status_endpoint": payload.get("status_endpoint"),
            }
        )

    def _fetch_evaluation_result(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        status_request = self._status_request_payload(request)
        payload = self._request_json(
            method="GET",
            path=f"/api/planner/executions/{status_request['execution_id']}/evaluation-result",
            json_payload=status_request,
        )
        outcome = str(payload.get("outcome") or "").strip()
        if outcome not in {"compliant", "non_compliant", "exception_required"}:
            raise TPPContractError(
                "TPP evaluation response is missing a supported outcome."
            )

        evaluation_result = {
            "evaluation_id": str(payload.get("request_id") or request.request_id),
            "proposal_id": str(payload.get("proposal_id") or request.proposal_id or ""),
            "status": outcome,
            "approval_requirements": [
                {
                    "role": str(item.get("required_role") or item.get("role") or "approver"),
                    "reason": str(item.get("summary") or item.get("reason") or "Approval required."),
                    "mandatory": True,
                }
                for item in payload.get("exception_requirements") or []
                if isinstance(item, dict)
            ],
            "failure_reasons": [
                {
                    "code": str(item.get("code") or "policy_blocker"),
                    "message": str(item.get("summary") or item.get("message") or "Policy blocker."),
                    "severity": "blocking",
                    "related_category": str(item.get("category") or ""),
                }
                for item in payload.get("blocking_issues") or []
                if isinstance(item, dict)
            ],
            "preferred_alternatives": [
                {
                    "category": str(item.get("category") or "policy"),
                    "summary": str(item.get("summary") or "Preferred alternative available."),
                    "rationale": str(item.get("rationale") or item.get("summary") or "Follow the suggested alternative."),
                    "comparable_ref": item.get("comparable_ref"),
                }
                for item in payload.get("preferred_alternatives") or []
                if isinstance(item, dict)
            ],
            "exception_guidance": [
                str(item.get("summary") or item.get("message") or "").strip()
                for item in (
                    list(payload.get("reoptimization_guidance") or [])
                    + list(payload.get("exception_requirements") or [])
                )
                if isinstance(item, dict) and str(item.get("summary") or item.get("message") or "").strip()
            ],
            "notes": [
                f"Planner evaluation outcome: {outcome}.",
                f"Underlying policy status: {str((payload.get('policy_result') or {}).get('status') or '').strip() or 'unknown'}.",
            ],
            "compliance_score": (
                1.0 if outcome == "compliant" else 0.45 if outcome == "exception_required" else 0.15
            ),
        }
        return TPPResponseEnvelope.from_dict(
            {
                "operation": request.operation,
                "request_id": request.request_id,
                "correlation_id": request.correlation_id.to_dict(),
                "transport_pattern": request.transport_pattern,
                "execution_status": {
                    "state": "succeeded",
                    "terminal": True,
                    "summary": f"Policy evaluation {outcome.replace('_', ' ')}.",
                    "external_status": "200 OK",
                    "updated_at": payload.get("generated_at"),
                },
                "result_payload": {
                    "trip_id": payload.get("trip_id") or request.trip_id,
                    "proposal_id": payload.get("proposal_id") or request.proposal_id,
                    "proposal_version": payload.get("proposal_version")
                    or status_request.get("proposal_version"),
                    "execution_id": payload.get("execution_id") or status_request.get("execution_id"),
                    "evaluation_result": evaluation_result,
                },
                "received_at": payload.get("generated_at"),
                "status_endpoint": payload.get("status_endpoint"),
            }
        )
