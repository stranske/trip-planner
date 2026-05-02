"""Client interfaces for Travel-Plan-Permission execution workflows."""

from __future__ import annotations

import math
import os
import random
import socket
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Callable, Literal, Protocol
import json
from urllib import error as urllib_error
from urllib import parse as urllib_parse
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

    VALID_ERROR_CODES = frozenset(
        {
            "timeout",
            "connection_error",
            "server_error",
            "breaker_open",
            "unauthorized",
            "invalid_response",
            "unknown",
        }
    )

    def __init__(
        self,
        message: str,
        *,
        error_code: Literal[
            "timeout",
            "connection_error",
            "server_error",
            "breaker_open",
            "unauthorized",
            "invalid_response",
            "unknown",
        ] = "unknown",
        status_code: int = 502,
        retryable: bool = False,
    ) -> None:
        if error_code not in self.VALID_ERROR_CODES:
            raise ValueError(
                "error_code must be one of "
                f"{sorted(self.VALID_ERROR_CODES)!r}, got {error_code!r}."
            )
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.retryable = retryable


class TPPConfigurationError(TPPTransportError):
    """Raised when live TPP transport is requested without runtime config."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="unknown", status_code=503, retryable=True)


class TPPContractError(TPPTransportError):
    """Raised when the upstream TPP service returns an invalid contract."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code="invalid_response",
            status_code=502,
            retryable=False,
        )


class TPPServiceUnavailableError(TPPTransportError):
    """Raised when the upstream TPP service cannot be reached."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code="connection_error",
            status_code=503,
            retryable=True,
        )


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise TPPConfigurationError(f"{name} must be a numeric value when provided.") from exc
    if not math.isfinite(value):
        raise TPPConfigurationError(f"{name} must be a finite numeric value when provided.")
    return value


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise TPPConfigurationError(f"{name} must be an integer value when provided.") from exc


@dataclass(slots=True)
class TPPTransportPolicy:
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 15.0
    max_attempts: int = 3
    backoff_initial_seconds: float = 0.5
    backoff_max_seconds: float = 4.0
    breaker_failure_threshold: int = 5
    breaker_reset_seconds: float = 30.0

    def __post_init__(self) -> None:
        for field_name in (
            "connect_timeout_seconds",
            "read_timeout_seconds",
            "breaker_reset_seconds",
        ):
            value = float(getattr(self, field_name))
            if not math.isfinite(value) or value <= 0:
                raise TPPConfigurationError(f"{field_name} must be a finite value greater than 0.")
            setattr(self, field_name, value)
        for field_name in ("backoff_initial_seconds", "backoff_max_seconds"):
            value = float(getattr(self, field_name))
            if not math.isfinite(value):
                raise TPPConfigurationError(f"{field_name} must be finite.")
            if value < 0:
                raise TPPConfigurationError(f"{field_name} must not be negative.")
            setattr(self, field_name, value)
        for field_name in ("max_attempts", "breaker_failure_threshold"):
            value = int(getattr(self, field_name))
            if value <= 0:
                raise TPPConfigurationError(f"{field_name} must be greater than 0.")
            setattr(self, field_name, value)

    @classmethod
    def from_env(cls) -> "TPPTransportPolicy":
        default_read_timeout = _env_float("TPP_TIMEOUT_SECONDS", 15.0)
        return cls(
            connect_timeout_seconds=_env_float("TPP_TRANSPORT_CONNECT_TIMEOUT_SECONDS", 5.0),
            read_timeout_seconds=_env_float(
                "TPP_TRANSPORT_READ_TIMEOUT_SECONDS", default_read_timeout
            ),
            max_attempts=_env_int("TPP_TRANSPORT_MAX_ATTEMPTS", 3),
            backoff_initial_seconds=_env_float("TPP_TRANSPORT_BACKOFF_INITIAL_SECONDS", 0.5),
            backoff_max_seconds=_env_float("TPP_TRANSPORT_BACKOFF_MAX_SECONDS", 4.0),
            breaker_failure_threshold=_env_int("TPP_TRANSPORT_BREAKER_FAILURE_THRESHOLD", 5),
            breaker_reset_seconds=_env_float("TPP_TRANSPORT_BREAKER_RESET_SECONDS", 30.0),
        )


class _CircuitBreaker:
    def __init__(self) -> None:
        self.failures = 0
        self.opened_at: float | None = None
        self.half_open = False
        self._half_open_trial_in_flight = False
        self._lock = threading.RLock()

    @property
    def state(self) -> str:
        with self._lock:
            if self.opened_at is None:
                return "closed"
            if self.half_open:
                return "half-open"
            return "open"

    def before_request(self, *, policy: TPPTransportPolicy, now: float, host: str) -> None:
        with self._lock:
            if self.opened_at is None:
                return
            if now - self.opened_at < policy.breaker_reset_seconds:
                raise TPPTransportError(
                    f"TPP circuit breaker is open for {host}; retry after the reset window.",
                    error_code="breaker_open",
                    status_code=503,
                    retryable=True,
                )
            self.half_open = True
            if self._half_open_trial_in_flight:
                raise TPPTransportError(
                    f"TPP circuit breaker is half-open for {host}; trial already in flight.",
                    error_code="breaker_open",
                    status_code=503,
                    retryable=True,
                )
            self._half_open_trial_in_flight = True

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_at = None
            self.half_open = False
            self._half_open_trial_in_flight = False

    def record_failure(self, *, policy: TPPTransportPolicy, now: float) -> None:
        with self._lock:
            if self.half_open:
                self.opened_at = now
                self.half_open = False
                self._half_open_trial_in_flight = False
                return
            self.failures += 1
            if self.failures >= policy.breaker_failure_threshold:
                self.opened_at = now
                self.half_open = False
                self._half_open_trial_in_flight = False


def tpp_transport_error_from_exception(
    exc: BaseException,
    *,
    operation: str,
    path: str | None = None,
) -> TPPTransportError | None:
    target = path or operation
    if isinstance(exc, TPPTransportError):
        return exc
    if isinstance(exc, urllib_error.HTTPError):
        try:
            body_excerpt = exc.read().decode("utf-8", errors="replace").strip()
        except OSError:
            body_excerpt = ""
        return _http_status_error(path=target, status_code=exc.code, body_excerpt=body_excerpt)
    if isinstance(exc, urllib_error.URLError):
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return TPPTransportError(
                f"TPP request for {target} timed out: {reason}.",
                error_code="timeout",
                status_code=504,
                retryable=True,
            )
        return TPPTransportError(
            f"TPP request for {target} failed: {exc}.",
            error_code="connection_error",
            status_code=503,
            retryable=True,
        )
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return TPPTransportError(
            f"TPP request for {target} timed out: {exc}.",
            error_code="timeout",
            status_code=504,
            retryable=True,
        )
    if isinstance(exc, (ConnectionError, OSError)):
        return TPPTransportError(
            f"TPP request for {target} failed: {exc}.",
            error_code="connection_error",
            status_code=503,
            retryable=True,
        )
    return None


def _http_status_error(*, path: str, status_code: int, body_excerpt: str) -> TPPTransportError:
    excerpt = body_excerpt.strip()
    if len(excerpt) > 280:
        excerpt = f"{excerpt[:277]}..."
    message = f"TPP request to {path} returned HTTP {status_code}: {excerpt or 'no response body'}"
    if status_code in {401, 403}:
        return TPPTransportError(
            message,
            error_code="unauthorized",
            status_code=status_code,
            retryable=False,
        )
    if 500 <= status_code <= 599:
        return TPPTransportError(
            message,
            error_code="server_error",
            status_code=503,
            retryable=True,
        )
    return TPPTransportError(
        message,
        error_code="unknown",
        status_code=502,
        retryable=False,
    )


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
            if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
                raise TPPConfigurationError(
                    "TPP_TIMEOUT_SECONDS must be a finite value greater than 0."
                )

        return cls(
            base_url=base_url.rstrip("/"),
            access_token=access_token,
            oidc_provider=oidc_provider,
            timeout_seconds=timeout_seconds,
        )


class HTTPTPPIntegrationClient(BaseTPPIntegrationClient):
    """Executes TPP operations over the planner-facing HTTP seam."""

    _breakers: ClassVar[dict[tuple[str, str, int], _CircuitBreaker]] = {}
    _default_breaker_registry_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        settings: TPPRuntimeSettings | None = None,
        *,
        policy: TPPTransportPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
        jitter: Callable[[float, float], float] | None = None,
        breaker_registry: dict[tuple[str, str, int], _CircuitBreaker] | None = None,
        breaker_registry_lock: threading.Lock | None = None,
    ) -> None:
        self.settings = settings or TPPRuntimeSettings.from_env()
        self.policy = policy or TPPTransportPolicy.from_env()
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic
        self._jitter = jitter or random.uniform
        self._breaker_registry = (
            breaker_registry if breaker_registry is not None else self._breakers
        )
        self._breaker_registry_lock = (
            breaker_registry_lock or threading.Lock()
            if breaker_registry is not None
            else self._default_breaker_registry_lock
        )

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

    def _dispatch(
        self, expected_operation: str, request: TPPRequestEnvelope
    ) -> TPPResponseEnvelope:
        try:
            return super()._dispatch(expected_operation, request)
        except TPPTransportError:
            raise
        except Exception as exc:
            transport_error = tpp_transport_error_from_exception(
                exc,
                operation=expected_operation,
            )
            if transport_error is None:
                raise
            raise transport_error from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-TPP-OIDC-Provider": self.settings.oidc_provider,
        }

    @staticmethod
    def _strip_none_values(payload: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if value is not None}

    @staticmethod
    def _extract_trip_plan_payload(payload: dict[str, Any], *, operation: str) -> dict[str, Any]:
        trip_plan = payload.pop("trip_plan", None)
        if not isinstance(trip_plan, dict):
            raise TPPContractError(
                f"Live TPP {operation} requires payload.trip_plan for the planner HTTP wrapper."
            )
        return trip_plan

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        json_payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.settings.base_url}{path}"
        breaker_key = self._breaker_key(url)
        with self._breaker_registry_lock:
            breaker = self._breaker_registry.setdefault(breaker_key, _CircuitBreaker())
        host_label = self._host_label(breaker_key)
        last_error: TPPTransportError | None = None

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                breaker.before_request(
                    policy=self.policy,
                    now=self._clock(),
                    host=host_label,
                )
                payload = self._send_json_request(
                    method=method,
                    path=path,
                    url=url,
                    json_payload=json_payload,
                )
            except TPPTransportError as exc:
                last_error = exc
                if exc.error_code != "breaker_open":
                    breaker.record_failure(policy=self.policy, now=self._clock())
                if (
                    exc.error_code == "breaker_open"
                    or not exc.retryable
                    or attempt >= self.policy.max_attempts
                ):
                    raise
                delay = self._retry_delay(attempt)
                if delay > 0:
                    self._sleep(delay)
                continue
            except (
                urllib_error.URLError,
                TimeoutError,
                socket.timeout,
                ConnectionError,
                OSError,
            ) as exc:
                transport_error = tpp_transport_error_from_exception(
                    exc,
                    operation=method,
                    path=path,
                ) or TPPTransportError(
                    f"TPP request to {path} failed: {exc}.",
                    error_code="unknown",
                    status_code=502,
                    retryable=False,
                )
                last_error = transport_error
                breaker.record_failure(policy=self.policy, now=self._clock())
                if not transport_error.retryable or attempt >= self.policy.max_attempts:
                    raise transport_error from exc
                delay = self._retry_delay(attempt)
                if delay > 0:
                    self._sleep(delay)
                continue
            except Exception as exc:
                transport_error = TPPTransportError(
                    f"TPP request to {path} failed unexpectedly: {exc}.",
                    error_code="unknown",
                    status_code=502,
                    retryable=False,
                )
                last_error = transport_error
                breaker.record_failure(policy=self.policy, now=self._clock())
                raise transport_error from exc
            breaker.record_success()
            return payload

        if last_error is not None:
            raise last_error
        raise TPPTransportError(
            f"TPP request to {path} failed without a typed transport result.",
            error_code="unknown",
            status_code=502,
            retryable=False,
        )

    def _send_json_request(
        self,
        *,
        method: str,
        path: str,
        url: str,
        json_payload: dict[str, Any],
    ) -> dict[str, Any]:
        body = json.dumps(json_payload).encode("utf-8")
        request = urllib_request.Request(
            url,
            data=body,
            headers=self._headers(),
            method=method,
        )
        try:
            with urllib_request.urlopen(
                request,
                timeout=self.policy.connect_timeout_seconds,
            ) as response:
                self._apply_read_timeout(response)
                status_code = response.status
                raw_body = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            try:
                raw_body = exc.read().decode("utf-8", errors="replace")
            except OSError:
                raw_body = ""
            raise _http_status_error(
                path=path,
                status_code=exc.code,
                body_excerpt=raw_body,
            ) from exc
        except (
            urllib_error.URLError,
            TimeoutError,
            socket.timeout,
            ConnectionError,
            OSError,
        ) as exc:
            transport_error = tpp_transport_error_from_exception(
                exc, operation="request", path=path
            )
            if transport_error is None:
                raise
            raise transport_error from exc
        except UnicodeDecodeError as exc:
            raise TPPContractError(
                f"TPP request to {path} returned a response body that is not valid UTF-8."
            ) from exc

        if status_code >= 400:
            raise _http_status_error(
                path=path,
                status_code=status_code,
                body_excerpt=raw_body,
            )

        try:
            payload = json.loads(raw_body)
        except ValueError:
            raise TPPContractError(f"TPP request to {path} returned a non-JSON response.")
        if not isinstance(payload, dict):
            raise TPPContractError(f"TPP request to {path} returned a non-object JSON payload.")
        return payload

    def _apply_read_timeout(self, response: Any) -> None:
        # urllib does not expose separate connect/read timeout knobs; apply read timeout
        # on the opened socket when accessible and otherwise fall back silently.
        sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if sock is None:
            return
        settimeout = getattr(sock, "settimeout", None)
        if callable(settimeout):
            settimeout(self.policy.read_timeout_seconds)

    def _retry_delay(self, attempt: int) -> float:
        delay = min(
            self.policy.backoff_initial_seconds * (2 ** max(attempt - 1, 0)),
            self.policy.backoff_max_seconds,
        )
        if delay <= 0:
            return 0.0
        return self._jitter(0.0, delay)

    @staticmethod
    def _breaker_key(url: str) -> tuple[str, str, int]:
        parsed = urllib_parse.urlsplit(url)
        scheme = parsed.scheme or "http"
        host = parsed.hostname or ""
        if not host:
            raise TPPContractError("TPP_BASE_URL must include a host.")
        port = parsed.port or (443 if scheme == "https" else 80)
        return (scheme, host, port)

    @staticmethod
    def _host_label(key: tuple[str, str, int]) -> str:
        scheme, host, port = key
        return f"{scheme}://{host}:{port}"

    def _policy_request_payload(self, request: TPPRequestEnvelope) -> dict[str, Any]:
        payload = dict(request.payload)
        trip_plan = self._extract_trip_plan_payload(payload, operation="policy snapshot")
        trip_id = payload.get("trip_id") or request.trip_id or trip_plan.get("trip_id")
        if trip_id in (None, ""):
            raise TPPContractError(
                "Live policy sync requires request.trip_id, payload.trip_id, "
                "or payload.trip_plan.trip_id."
            )
        snapshot_request = self._strip_none_values(
            {
                "trip_id": trip_id,
                "requested_at": payload.get("requested_at") or request.submitted_at,
                "snapshot_generated_at": payload.get("snapshot_generated_at"),
                "known_policy_version": payload.get("known_policy_version"),
                "invalidate_reason": payload.get("invalidate_reason"),
            }
        )
        return {"trip_plan": trip_plan, "request": snapshot_request}

    def _proposal_request_payload(self, request: TPPRequestEnvelope) -> dict[str, Any]:
        payload = dict(request.payload)
        trip_plan = self._extract_trip_plan_payload(payload, operation="proposal submission")
        proposal_version = payload.pop("proposal_version", None)
        payload.pop("trip_id", None)
        payload.pop("proposal_id", None)
        payload.pop("request_id", None)
        payload.pop("correlation_id", None)
        payload.pop("transport_pattern", None)
        payload.pop("organization_id", None)
        payload.pop("submitted_at", None)
        request_payload = self._strip_none_values(
            {
                "trip_id": request.trip_id or trip_plan.get("trip_id"),
                "proposal_id": request.proposal_id,
                "proposal_version": proposal_version,
                "payload": payload,
                "request_id": request.request_id,
                "correlation_id": request.correlation_id.to_dict(),
                "transport_pattern": request.transport_pattern,
                "organization_id": request.organization_id,
                "submitted_at": request.submitted_at,
            }
        )
        if (
            request_payload.get("trip_id") in (None, "")
            or request_payload.get("proposal_id") in (None, "")
            or request_payload.get("proposal_version") in (None, "")
        ):
            raise TPPContractError(
                "Live proposal submission requires trip_id, proposal_id, and proposal_version."
            )
        return {"trip_plan": trip_plan, "request": request_payload}

    def _status_request_payload(self, request: TPPRequestEnvelope) -> dict[str, Any]:
        payload = dict(request.payload)
        payload.setdefault("trip_id", request.trip_id)
        payload.setdefault("proposal_id", request.proposal_id)
        payload.setdefault("proposal_version", payload.get("proposal_version"))
        payload.setdefault("execution_id", payload.get("execution_id"))
        payload.setdefault("request_id", request.request_id)
        if request.submitted_at is not None:
            payload.setdefault("requested_at", request.submitted_at)
        payload = self._strip_none_values(payload)
        if payload.get("trip_id") in (None, "") or payload.get("proposal_id") in (None, ""):
            raise TPPContractError("Live TPP status operations require trip_id and proposal_id.")
        if payload.get("proposal_version") in (None, ""):
            raise TPPContractError("Live TPP status operations require payload.proposal_version.")
        if payload.get("execution_id") in (None, ""):
            raise TPPContractError("Live TPP status operations require payload.execution_id.")
        return payload

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
            raise TPPContractError("TPP policy snapshot response is missing versioning metadata.")

        policy_version = str(versioning.get("policy_version") or "").strip()
        if not policy_version:
            raise TPPContractError("TPP policy snapshot response is missing policy_version.")

        organization_context_raw = request.payload.get("organization_context")
        organization_context = (
            organization_context_raw if isinstance(organization_context_raw, dict) else {}
        )
        organization_id = (
            request.organization_id
            or str(organization_context.get("organization_id") or "").strip()
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
            raise TPPContractError("TPP evaluation response is missing a supported outcome.")

        evaluation_result = {
            "evaluation_id": str(payload.get("request_id") or request.request_id),
            "proposal_id": str(payload.get("proposal_id") or request.proposal_id or ""),
            "status": outcome,
            "approval_requirements": [
                {
                    "role": str(item.get("required_role") or item.get("role") or "approver"),
                    "reason": str(
                        item.get("summary") or item.get("reason") or "Approval required."
                    ),
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
                    "rationale": str(
                        item.get("rationale")
                        or item.get("summary")
                        or "Follow the suggested alternative."
                    ),
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
                if isinstance(item, dict)
                and str(item.get("summary") or item.get("message") or "").strip()
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
                    "execution_id": payload.get("execution_id")
                    or status_request.get("execution_id"),
                    "evaluation_result": evaluation_result,
                },
                "received_at": payload.get("generated_at"),
                "status_endpoint": payload.get("status_endpoint"),
            }
        )
