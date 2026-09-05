import json
from pathlib import Path
from typing import Any

import pytest

from trip_planner.app.services.policy import (
    PersistedPolicyStateValidationError,
    _normalize_policy_requirements,
)
from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    HTTPTPPIntegrationClient,
    PolicySyncError,
    TPPContractError,
    TPPPolicySyncService,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
    TPPRuntimeSettings,
    summarize_policy_import,
)
from trip_planner.integrations.tpp.policy_sync import parse_policy_requirements


def _fixture_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp" / "policy" / name
    )


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


class FakeTPPPolicyClient(BaseTPPIntegrationClient):
    def __init__(self, response: TPPResponseEnvelope) -> None:
        self.response = response
        self.calls: list[str] = []

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        self.calls.append(request.operation)
        return self.response


def test_import_standard_policy_sync_snapshot() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    imported = service.import_policy_constraints(request)
    summary = summarize_policy_import(imported, "2026-02-15T14:00:00Z")

    assert imported.constraint_set.policy_id == "policy-standard-2026-02"
    assert imported.organization_context.comparable_requirements == {
        "airfare": 2,
        "lodging": 2,
    }
    assert imported.constraint_set.required_booking_channels == ["Navan", "Concur"]
    assert imported.organization_context.policy_status == "pass"
    assert imported.organization_context.contract_version == "2026-04-11"
    assert imported.organization_context.booking_requirements[0].code == "approved_booking_channel"
    assert summary["is_stale"] is False
    assert summary["documentation_rules"] == [
        "retain_receipts",
        "attach_comparables",
    ]
    assert summary["policy_status"] == "pass"
    assert summary["compatible_with_planner_cache"] is True
    assert summary["blocking_issues"] == []


def test_policy_sync_rejects_unsupported_contract_version() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["response"]["result_payload"]["organization_context"]["contract_version"] = "1999-01-01"
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])

    with pytest.raises(ValueError, match="Unsupported TPP policy contract version"):
        TPPPolicySyncService(FakeTPPPolicyClient(response)).import_policy_constraints(request)


@pytest.mark.parametrize("value", ["false", 0])
def test_policy_sync_rejects_malformed_cache_compatibility_values(value: object) -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["response"]["result_payload"]["organization_context"][
        "compatible_with_planner_cache"
    ] = value
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])

    with pytest.raises(ValueError, match="compatible_with_planner_cache must be a boolean"):
        TPPPolicySyncService(FakeTPPPolicyClient(response)).import_policy_constraints(request)


def test_import_stricter_org_policy_preserves_limits_and_triggers() -> None:
    fixture = _load_fixture("strict_policy_sync.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    imported = service.import_policy_constraints(request)

    assert imported.constraint_set.airfare_rules["max_cabin"] == "economy"
    assert imported.constraint_set.lodging_rules["max_nightly_rate_usd"] == 210
    assert imported.organization_context.class_of_service_limits["air"] == "economy"
    assert imported.organization_context.approval_triggers == [
        "international_travel",
        "lodging_above_cap",
        "vice_president_preapproval",
    ]


def test_invalidated_policy_snapshot_is_marked_stale() -> None:
    fixture = _load_fixture("invalidated_policy_sync.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    imported = service.import_policy_constraints(request)

    assert imported.is_stale("2026-02-18T12:00:00Z") is True
    assert imported.freshness.status == "invalidated"
    assert imported.freshness.invalidation_reason == "manual_policy_recall"


def test_policy_sync_rejects_malformed_comparable_requirements() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["response"]["result_payload"]["organization_context"]["comparable_requirements"][
        "lodging"
    ] = "two"
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    with pytest.raises(ValueError, match="comparable_requirements\\[lodging\\]"):
        service.import_policy_constraints(request)


def test_policy_sync_rejects_missing_constraint_set_payload() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    del fixture["response"]["result_payload"]["constraint_set"]
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    with pytest.raises(ValueError, match="result_payload.constraint_set"):
        service.import_policy_constraints(request)


def test_policy_sync_rejects_non_succeeded_execution_status() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["response"]["execution_status"]["state"] = "deferred"
    fixture["response"]["execution_status"]["terminal"] = False
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    with pytest.raises(PolicySyncError, match="succeeded execution_status"):
        service.import_policy_constraints(request)


def test_policy_sync_rejects_mismatched_request_id() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    fixture["response"]["request_id"] = "policy-sync-req-other"
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    with pytest.raises(PolicySyncError, match="response.request_id"):
        service.import_policy_constraints(request)


def test_policy_sync_rejects_mismatched_correlation_id() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    fixture["response"]["correlation_id"]["value"] = "corr-policy-sync-other"
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    with pytest.raises(PolicySyncError, match="response.correlation_id"):
        service.import_policy_constraints(request)


@pytest.mark.parametrize(
    ("flags", "expected_severity"),
    [
        ({"blocking": True}, "blocking"),
        ({"blocking": True, "severity": "warning"}, "blocking"),
        ({"severity": "error"}, "blocking"),
        ({"severity": "blocking"}, "blocking"),
        ({"blocking": False, "severity": "blocking"}, "blocking"),
        ({"severity": "warning"}, "warning"),
        ({"blocking": False}, "warning"),
        ({}, "warning"),
    ],
)
def test_http_and_fixture_paths_normalize_blocking_requirement_severity_identically(
    monkeypatch: pytest.MonkeyPatch,
    flags: dict[str, Any],
    expected_severity: str,
) -> None:
    requirement = {"code": " booking-channel ", "summary": " Use approved booking ", **flags}
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["request"]["payload"]["trip_plan"] = {"trip_id": "trip-policy-parser"}
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    fixture["response"]["result_payload"]["organization_context"]["booking_requirements"] = [
        requirement
    ]
    fixture_import = TPPPolicySyncService(
        FakeTPPPolicyClient(TPPResponseEnvelope.from_dict(fixture["response"]))
    ).import_policy_constraints(request)

    http_client = HTTPTPPIntegrationClient(
        TPPRuntimeSettings(
            base_url="https://tpp.example", access_token="test-token", oidc_provider="okta"
        )
    )
    snapshot = {
        "versioning": {
            "policy_version": "2026-02",
            "contract_version": "2026-04-11",
            "compatible_with_planner_cache": True,
        },
        "generated_at": "2026-02-15T12:00:00Z",
        "policy_status": "pass",
        "booking_requirements": [requirement],
    }
    monkeypatch.setattr(http_client, "_request_json", lambda **_kwargs: snapshot)
    http_import = TPPPolicySyncService(http_client).import_policy_constraints(request)
    expected = [
        {
            "code": "booking-channel",
            "summary": "Use approved booking",
            "severity": expected_severity,
        }
    ]
    assert [
        item.to_dict() for item in fixture_import.organization_context.booking_requirements
    ] == expected
    assert [
        item.to_dict() for item in http_import.organization_context.booking_requirements
    ] == expected
    # The DB reload path must accept the same input and the canonical stored output.
    for stored in ([requirement], expected):
        reloaded = _normalize_policy_requirements(stored, field_name="booking_requirements")
        assert [item.to_dict() for item in reloaded] == expected


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        [None],
        [{"code": 12, "summary": "Rule", "severity": "warning"}],
        [{"code": "rule", "summary": "  ", "severity": "warning"}],
        [{"code": "rule", "summary": "Rule", "severity": "critical"}],
        [{"code": "rule", "summary": "Rule", "severity": None}],
        [{"code": "rule", "summary": "Rule", "blocking": "true"}],
    ],
)
def test_requirement_paths_reject_malformed_values_with_boundary_error_types(payload: Any) -> None:
    with pytest.raises(ValueError):
        parse_policy_requirements(payload, "booking_requirements")
    with pytest.raises(TPPContractError):
        HTTPTPPIntegrationClient._adapt_policy_requirements(
            payload, field_name="booking_requirements"
        )
    with pytest.raises(PersistedPolicyStateValidationError):
        _normalize_policy_requirements(payload, field_name="booking_requirements")
