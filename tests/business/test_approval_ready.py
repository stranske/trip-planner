import json
from pathlib import Path

from trip_planner.business import (
    ApprovalReadyPackage,
    BusinessTravelProfile,
    PolicyEvaluationResult,
    TripPlanProposal,
    build_approval_ready_package,
)

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "business"


def _fixture_path(name: str) -> Path:
    return _FIXTURES_DIR / name


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def _build_package(name: str) -> tuple[dict, ApprovalReadyPackage]:
    payload = _load_fixture(name)
    profile = BusinessTravelProfile.from_dict(payload["profile"])
    proposal = TripPlanProposal.from_dict(payload["proposal"])
    evaluation = PolicyEvaluationResult.from_dict(payload["evaluation_result"])
    package = build_approval_ready_package(profile, proposal, evaluation)
    return payload, package


def test_builds_clean_approval_ready_package() -> None:
    payload, package = _build_package("approval_ready_clean.json")
    expected = payload["expected_package"]

    assert package.package_status == expected["package_status"]
    assert package.scenario_posture == expected["scenario_posture"]
    assert package.approval_roles == expected["approval_roles"]
    assert package.required_receipt_categories == expected["required_receipt_categories"]
    assert package.justification_fields == expected["justification_fields"]
    assert package.package_summary[0].startswith("Business justification:")
    assert "Policy status: compliant" in package.package_summary

    readiness_statuses = {item.key: item.status for item in package.readiness_checks}
    assert readiness_statuses == expected["readiness_check_statuses"]


def test_builds_exception_ready_package() -> None:
    payload, package = _build_package("approval_ready_exception.json")
    expected = payload["expected_package"]

    assert package.package_status == expected["package_status"]
    assert package.scenario_posture == expected["scenario_posture"]
    assert package.approval_roles == expected["approval_roles"]
    assert package.required_receipt_categories == expected["required_receipt_categories"]
    assert package.justification_fields == expected["justification_fields"]
    assert package.requested_exception is not None
    assert package.preferred_alternatives[0].comparable_ref == "lodging:within-cap-motel"
    assert package.failure_reasons[0].severity == "warning"

    readiness_statuses = {item.key: item.status for item in package.readiness_checks}
    assert readiness_statuses == expected["readiness_check_statuses"]


def test_approval_ready_package_rejects_mismatched_proposal_ids() -> None:
    payload = _load_fixture("approval_ready_clean.json")
    profile = BusinessTravelProfile.from_dict(payload["profile"])
    proposal = TripPlanProposal.from_dict(payload["proposal"])
    evaluation = PolicyEvaluationResult.from_dict(payload["evaluation_result"])
    evaluation = PolicyEvaluationResult.from_dict(
        {
            **evaluation.to_dict(),
            "proposal_id": "other-proposal",
        }
    )

    try:
        build_approval_ready_package(profile, proposal, evaluation)
    except ValueError as exc:
        assert "proposal_id" in str(exc)
    else:
        raise AssertionError("mismatched proposal ids should fail approval packaging")


def test_empty_booking_channels_require_attention() -> None:
    payload = _load_fixture("approval_ready_clean.json")
    profile = BusinessTravelProfile.from_dict(payload["profile"])
    proposal = TripPlanProposal.from_dict(payload["proposal"])
    proposal.booking_channel_summaries = []
    evaluation = PolicyEvaluationResult.from_dict(payload["evaluation_result"])

    package = build_approval_ready_package(profile, proposal, evaluation)

    readiness_checks = {item.key: item for item in package.readiness_checks}
    booking_channels = readiness_checks["booking_channels"]
    assert booking_channels.status == "attention"
    assert booking_channels.notes == ["No booking channels documented"]
