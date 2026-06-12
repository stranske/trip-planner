"""Shared ranking-engine validation guards."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from trip_planner.candidates import CandidateSet
from trip_planner.options import InventoryBundle

if TYPE_CHECKING:
    from trip_planner.itinerary.feasibility import FeasibilityAssessment


class BaseRankingEngine:
    """Own validation guards common to leisure and business ranking engines."""

    def validate_feasibility_outputs(
        self,
        feasibility_outputs: (
            Mapping[str, FeasibilityAssessment] | Sequence[FeasibilityAssessment] | None
        ),
    ) -> dict[str, FeasibilityAssessment]:
        from trip_planner.itinerary.feasibility import FeasibilityAssessment

        if feasibility_outputs is None:
            return {}
        if isinstance(feasibility_outputs, Mapping):
            values = dict(feasibility_outputs)
        elif isinstance(feasibility_outputs, Sequence):
            values = {item.bundle_id: item for item in feasibility_outputs}
        else:
            raise ValueError(
                "feasibility_outputs must be a mapping, a sequence of FeasibilityAssessment values, or None"
            )
        if any(not isinstance(item, FeasibilityAssessment) for item in values.values()):
            raise ValueError("feasibility_outputs must contain FeasibilityAssessment instances")
        return values

    def validate_candidate_set(self, candidate_set: CandidateSet) -> CandidateSet:
        if not isinstance(candidate_set, CandidateSet):
            raise ValueError("candidate_set must be a CandidateSet")
        return candidate_set

    def validate_bundles(self, bundles: Sequence[InventoryBundle]) -> list[InventoryBundle]:
        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence):
            raise ValueError("bundles must be a sequence of InventoryBundle instances")
        bundle_list = list(bundles)
        if not bundle_list:
            raise ValueError("bundles must contain at least one InventoryBundle")
        if any(not isinstance(item, InventoryBundle) for item in bundle_list):
            raise ValueError("bundles must contain InventoryBundle instances")
        return bundle_list
