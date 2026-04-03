"""Local simulator for policy-evaluation contract testing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from trip_planner._validators import require_non_empty, require_strings

from .approval_ready import ApprovalReadyPackage, build_approval_ready_package
from .policy_contracts import PolicyConstraintSet, PolicyEvaluationResult, TripPlanProposal
from .profile import BusinessTravelProfile


@dataclass(slots=True)
class PolicySimulationCase:
    case_id: str
    description: str
    evaluation_result: PolicyEvaluationResult
    fixture_proposal: TripPlanProposal | None = None
    fixture_constraint_set: PolicyConstraintSet | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.case_id, "case_id")
        require_non_empty(self.description, "description")
        if not isinstance(self.evaluation_result, PolicyEvaluationResult):
            raise ValueError("evaluation_result must be a PolicyEvaluationResult")
        if self.fixture_proposal is not None and not isinstance(
            self.fixture_proposal, TripPlanProposal
        ):
            raise ValueError("fixture_proposal must be a TripPlanProposal when provided")
        if self.fixture_constraint_set is not None and not isinstance(
            self.fixture_constraint_set, PolicyConstraintSet
        ):
            raise ValueError("fixture_constraint_set must be a PolicyConstraintSet when provided")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicySimulationCase":
        notes = payload.get("notes", [])
        if not isinstance(notes, list):
            raise ValueError("notes must be provided as a list")
        return cls(
            case_id=payload["case_id"],
            description=payload["description"],
            evaluation_result=PolicyEvaluationResult.from_dict(payload["evaluation_result"]),
            fixture_proposal=(
                TripPlanProposal.from_dict(payload["fixture_proposal"])
                if payload.get("fixture_proposal")
                else None
            ),
            fixture_constraint_set=(
                PolicyConstraintSet(**payload["fixture_constraint_set"])
                if payload.get("fixture_constraint_set")
                else None
            ),
            notes=list(notes),
        )


@dataclass(slots=True)
class SimulatedPolicyRun:
    case_id: str
    evaluation_result: PolicyEvaluationResult
    approval_package: ApprovalReadyPackage


class PolicyEvaluationSimulator:
    def __init__(self, cases: list[PolicySimulationCase]) -> None:
        if not cases:
            raise ValueError("cases must contain at least one PolicySimulationCase")
        self._cases = {case.case_id: case for case in cases}
        if len(self._cases) != len(cases):
            raise ValueError("case_id values must be unique")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyEvaluationSimulator":
        cases_payload = payload["cases"]
        if not isinstance(cases_payload, list):
            raise ValueError("cases must be a list of case payloads")
        cases = [PolicySimulationCase.from_dict(item) for item in cases_payload]
        return cls(cases)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "PolicyEvaluationSimulator":
        import json

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    def case_ids(self) -> list[str]:
        return sorted(self._cases)

    def evaluate(self, proposal: TripPlanProposal, *, case_id: str) -> PolicyEvaluationResult:
        if case_id not in self._cases:
            available_case_ids = self.case_ids()
            raise ValueError(
                f"Unknown case_id {case_id!r}. Available case_ids: {available_case_ids}"
            )
        case = self._cases[case_id]
        _validate_simulated_proposal_shape(proposal, case.fixture_proposal)
        payload = case.evaluation_result.to_dict()
        payload["proposal_id"] = proposal.proposal_id
        return PolicyEvaluationResult.from_dict(payload)

    def simulate_round_trip(
        self,
        *,
        case_id: str,
        profile: BusinessTravelProfile,
        proposal: TripPlanProposal,
        package_id: str | None = None,
        scenario_posture: str | None = None,
    ) -> SimulatedPolicyRun:
        evaluation_result = self.evaluate(proposal, case_id=case_id)
        approval_package = build_approval_ready_package(
            profile,
            proposal,
            evaluation_result,
            package_id=package_id,
            scenario_posture=scenario_posture,
        )
        return SimulatedPolicyRun(
            case_id=case_id,
            evaluation_result=evaluation_result,
            approval_package=approval_package,
        )


def _validate_simulated_proposal_shape(
    proposal: TripPlanProposal,
    fixture_proposal: TripPlanProposal | None,
) -> None:
    if fixture_proposal is None:
        return
    proposal_categories = {item.category for item in proposal.selected_options}
    fixture_categories = {item.category for item in fixture_proposal.selected_options}
    if proposal_categories != fixture_categories:
        raise ValueError(
            "proposal selected option categories do not match the simulator fixture case"
        )
    if (proposal.requested_exception is None) != (fixture_proposal.requested_exception is None):
        raise ValueError(
            "proposal exception posture does not match the simulator fixture case"
        )
