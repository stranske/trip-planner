"""Policy-constraint import scaffolding for Travel-Plan-Permission."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_string_mapping,
    require_strings,
)
from trip_planner.business.policy_contracts import PolicyConstraintSet

from .client import TPPIntegrationClient
from .contracts import TPPRequestEnvelope, TPPResponseEnvelope

POLICY_SYNC_STATES: tuple[str, ...] = ("current", "stale", "invalidated")


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be provided as a mapping")
    return dict(value)


def _optional_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    return _require_mapping(value, field_name)


def _require_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be provided as a list")
    values = list(value)
    require_strings(values, field_name)
    return values


def _optional_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    return _require_string_list(value, field_name)


def _parse_timestamp(value: str, field_name: str) -> datetime:
    require_non_empty(value, field_name)
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(UTC)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc


def _optional_timestamp(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    return _parse_timestamp(value, field_name)


def _serialize_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class PolicyFreshness:
    snapshot_version: str
    captured_at: str
    fresh_until: str | None = None
    invalidated_at: str | None = None
    invalidation_reason: str | None = None
    status: str = "current"

    def __post_init__(self) -> None:
        require_non_empty(self.snapshot_version, "snapshot_version")
        _parse_timestamp(self.captured_at, "captured_at")
        if self.status not in POLICY_SYNC_STATES:
            raise ValueError(f"status must be one of {POLICY_SYNC_STATES}")
        if self.fresh_until is not None:
            fresh_until = _parse_timestamp(self.fresh_until, "fresh_until")
            captured_at = _parse_timestamp(self.captured_at, "captured_at")
            if fresh_until < captured_at:
                raise ValueError("fresh_until must not precede captured_at")
        if self.invalidated_at is not None:
            invalidated_at = _parse_timestamp(self.invalidated_at, "invalidated_at")
            captured_at = _parse_timestamp(self.captured_at, "captured_at")
            if invalidated_at < captured_at:
                raise ValueError("invalidated_at must not precede captured_at")
            require_non_empty(self.invalidation_reason or "", "invalidation_reason")
        if self.status == "invalidated" and self.invalidated_at is None:
            raise ValueError("invalidated status requires invalidated_at")

    def is_stale(self, reference_time: str | datetime | None = None) -> bool:
        if self.status in {"stale", "invalidated"}:
            return True
        if self.invalidated_at is not None:
            return True
        if self.fresh_until is None:
            return False
        if reference_time is None:
            ref = datetime.now(UTC)
        elif isinstance(reference_time, datetime):
            ref = reference_time.astimezone(UTC)
        else:
            ref = _parse_timestamp(reference_time, "reference_time")
        return _parse_timestamp(self.fresh_until, "fresh_until") <= ref

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OrganizationContextSnapshot:
    organization_id: str
    approved_channels: list[str] = field(default_factory=list)
    comparable_requirements: dict[str, int] = field(default_factory=dict)
    documentation_rules: list[str] = field(default_factory=list)
    approval_triggers: list[str] = field(default_factory=list)
    comfort_preferences: dict[str, Any] = field(default_factory=dict)
    class_of_service_limits: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.organization_id, "organization_id")
        require_strings(self.approved_channels, "approved_channels")
        require_strings(self.documentation_rules, "documentation_rules")
        require_strings(self.approval_triggers, "approval_triggers")
        require_string_mapping(self.comfort_preferences, "comfort_preferences")
        require_string_mapping(self.class_of_service_limits, "class_of_service_limits")
        require_string_mapping(self.metadata, "metadata")
        if any(
            not isinstance(key, str) or not key for key in self.comparable_requirements
        ):
            raise ValueError("comparable_requirements must use non-empty string keys")
        for key, value in self.comparable_requirements.items():
            if not isinstance(value, int):
                raise ValueError(f"comparable_requirements[{key}] must be an integer")
            require_non_negative(value, f"comparable_requirements[{key}]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PolicyConstraintImport:
    constraint_set: PolicyConstraintSet
    organization_context: OrganizationContextSnapshot
    freshness: PolicyFreshness
    source_request_id: str
    source_correlation_id: str
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.constraint_set, PolicyConstraintSet):
            raise ValueError("constraint_set must be a PolicyConstraintSet")
        if not isinstance(self.organization_context, OrganizationContextSnapshot):
            raise ValueError(
                "organization_context must be an OrganizationContextSnapshot"
            )
        if not isinstance(self.freshness, PolicyFreshness):
            raise ValueError("freshness must be a PolicyFreshness")
        require_non_empty(self.source_request_id, "source_request_id")
        require_non_empty(self.source_correlation_id, "source_correlation_id")
        self.raw_payload = _optional_mapping(self.raw_payload, "raw_payload")

    @property
    def organization_id(self) -> str:
        return self.constraint_set.organization_id

    def is_stale(self, reference_time: str | datetime | None = None) -> bool:
        return self.freshness.is_stale(reference_time)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["constraint_set"] = self.constraint_set.to_dict()
        payload["organization_context"] = self.organization_context.to_dict()
        payload["freshness"] = self.freshness.to_dict()
        return payload


class PolicySyncError(ValueError):
    """Raised when a TPP policy import cannot be normalized safely."""


class TPPPolicySyncService:
    """Imports TPP policy responses into ranking-ready local contracts."""

    def __init__(self, client: TPPIntegrationClient) -> None:
        self.client = client

    def import_policy_constraints(
        self, request: TPPRequestEnvelope
    ) -> PolicyConstraintImport:
        response = self.client.fetch_policy_constraints(request)
        return self.normalize_response(request, response)

    def normalize_response(
        self, request: TPPRequestEnvelope, response: TPPResponseEnvelope
    ) -> PolicyConstraintImport:
        if request.operation != "fetch_policy_constraints":
            raise PolicySyncError(
                "request.operation must be 'fetch_policy_constraints'"
            )
        if response.operation != "fetch_policy_constraints":
            raise PolicySyncError(
                "response.operation must be 'fetch_policy_constraints'"
            )
        if response.execution_status.state != "succeeded":
            raise PolicySyncError("policy imports require a succeeded execution_status")

        payload = _require_mapping(response.result_payload, "result_payload")
        constraint_payload = _require_mapping(
            payload.get("constraint_set"), "result_payload.constraint_set"
        )
        context_payload = _optional_mapping(
            payload.get("organization_context"),
            "result_payload.organization_context",
        )
        freshness_payload = _require_mapping(
            payload.get("freshness"), "result_payload.freshness"
        )

        organization_id = constraint_payload.get(
            "organization_id"
        ) or context_payload.get("organization_id")
        if (
            request.organization_id is not None
            and organization_id != request.organization_id
        ):
            raise PolicySyncError(
                "response organization_id does not match request.organization_id"
            )

        constraint_set = PolicyConstraintSet(
            policy_id=constraint_payload["policy_id"],
            organization_id=organization_id,
            policy_version=constraint_payload["policy_version"],
            required_booking_channels=_optional_string_list(
                constraint_payload.get("required_booking_channels")
                or context_payload.get("approved_channels"),
                "required_booking_channels",
            ),
            airfare_rules=_optional_mapping(
                constraint_payload.get("airfare_rules"), "airfare_rules"
            ),
            lodging_rules=_optional_mapping(
                constraint_payload.get("lodging_rules"), "lodging_rules"
            ),
            ground_transport_rules=_optional_mapping(
                constraint_payload.get("ground_transport_rules"),
                "ground_transport_rules",
            ),
            meal_rules=_optional_mapping(
                constraint_payload.get("meal_rules"), "meal_rules"
            ),
            approval_rules=_optional_string_list(
                constraint_payload.get("approval_rules")
                or context_payload.get("approval_triggers"),
                "approval_rules",
            ),
            documentation_rules=_optional_string_list(
                constraint_payload.get("documentation_rules")
                or context_payload.get("documentation_rules"),
                "documentation_rules",
            ),
            allowed_exception_types=_optional_string_list(
                constraint_payload.get("allowed_exception_types"),
                "allowed_exception_types",
            ),
        )

        organization_context = OrganizationContextSnapshot(
            organization_id=organization_id,
            approved_channels=_optional_string_list(
                context_payload.get("approved_channels")
                or constraint_payload.get("required_booking_channels"),
                "approved_channels",
            ),
            comparable_requirements={
                key: value
                for key, value in _optional_mapping(
                    context_payload.get("comparable_requirements"),
                    "comparable_requirements",
                ).items()
            },
            documentation_rules=_optional_string_list(
                context_payload.get("documentation_rules")
                or constraint_payload.get("documentation_rules"),
                "organization_context.documentation_rules",
            ),
            approval_triggers=_optional_string_list(
                context_payload.get("approval_triggers")
                or constraint_payload.get("approval_rules"),
                "approval_triggers",
            ),
            comfort_preferences=_optional_mapping(
                context_payload.get("comfort_preferences"), "comfort_preferences"
            ),
            class_of_service_limits=_optional_mapping(
                context_payload.get("class_of_service_limits"),
                "class_of_service_limits",
            ),
            metadata=_optional_mapping(context_payload.get("metadata"), "metadata"),
        )

        freshness = PolicyFreshness(
            snapshot_version=freshness_payload.get(
                "snapshot_version", constraint_set.policy_version
            ),
            captured_at=freshness_payload.get("captured_at")
            or response.received_at
            or response.execution_status.updated_at
            or request.submitted_at
            or "",
            fresh_until=freshness_payload.get("fresh_until"),
            invalidated_at=freshness_payload.get("invalidated_at"),
            invalidation_reason=freshness_payload.get("invalidation_reason"),
            status=freshness_payload.get("status", "current"),
        )

        return PolicyConstraintImport(
            constraint_set=constraint_set,
            organization_context=organization_context,
            freshness=freshness,
            source_request_id=response.request_id,
            source_correlation_id=response.correlation_id.value,
            raw_payload=payload,
        )


def summarize_policy_import(
    imported: PolicyConstraintImport, reference_time: str | datetime | None = None
) -> dict[str, Any]:
    """Expose a compact summary for ranking and orchestration handoff."""

    summary = {
        "organization_id": imported.organization_id,
        "policy_id": imported.constraint_set.policy_id,
        "policy_version": imported.constraint_set.policy_version,
        "approved_channels": list(imported.organization_context.approved_channels),
        "approval_triggers": list(imported.organization_context.approval_triggers),
        "documentation_rules": list(imported.constraint_set.documentation_rules),
        "comparable_requirements": dict(
            imported.organization_context.comparable_requirements
        ),
        "is_stale": imported.is_stale(reference_time),
        "freshness": imported.freshness.to_dict(),
    }
    summary["freshness"]["captured_at"] = _serialize_timestamp(
        _parse_timestamp(imported.freshness.captured_at, "captured_at")
    )
    if imported.freshness.fresh_until is not None:
        summary["freshness"]["fresh_until"] = _serialize_timestamp(
            _parse_timestamp(imported.freshness.fresh_until, "fresh_until")
        )
    if imported.freshness.invalidated_at is not None:
        summary["freshness"]["invalidated_at"] = _serialize_timestamp(
            _parse_timestamp(imported.freshness.invalidated_at, "invalidated_at")
        )
    return summary
