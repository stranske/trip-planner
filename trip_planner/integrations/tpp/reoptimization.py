"""Planner-side reoptimization scaffolding for Travel-Plan-Permission results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from trip_planner._validators import require_non_empty, require_strings
from trip_planner.business.policy_contracts import PolicyEvaluationResult, TripPlanProposal
from trip_planner.state import ScenarioArtifactRefs, ScenarioComparison, ScenarioVersion

REACTION_KINDS: tuple[str, ...] = (
    "rerank",
    "narrow_candidates",
    "regenerate_scenario",
    "create_exception_candidate",
    "manual_review",
)
BUSINESS_SCENARIO_LABELS: tuple[str, ...] = ("compliant_first", "exception_nearest")


def _dedupe(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value and value not in ordered:
            ordered.append(value)
    return ordered


def _validate_ref_mapping(mapping: dict[str, list[str]], field_name: str) -> None:
    if not isinstance(mapping, dict):
        raise ValueError(f"{field_name} must be a mapping")
    for key, values in mapping.items():
        require_non_empty(key, f"{field_name} key")
        if not isinstance(values, list):
            raise ValueError(f"{field_name}[{key}] must be a list of strings")
        require_strings(values, f"{field_name}[{key}]")


@dataclass(slots=True)
class PolicyReoptimizationContext:
    source_version: ScenarioVersion
    comparable_refs: dict[str, list[str]] = field(default_factory=dict)
    justification_refs: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source_version, ScenarioVersion):
            raise ValueError("source_version must be a ScenarioVersion")
        if self.source_version.label not in BUSINESS_SCENARIO_LABELS:
            raise ValueError(f"source_version.label must be one of {BUSINESS_SCENARIO_LABELS}")
        _validate_ref_mapping(self.comparable_refs, "comparable_refs")
        _validate_ref_mapping(self.justification_refs, "justification_refs")


@dataclass(slots=True)
class PolicyReoptimizationPlan:
    source_version: ScenarioVersion
    proposal_id: str
    evaluation_id: str
    reaction_kind: str
    target_label: str
    comparison_outcome: str
    target_title: str
    candidate_categories: list[str] = field(default_factory=list)
    ranking_focus_areas: list[str] = field(default_factory=list)
    preserved_comparable_refs: list[str] = field(default_factory=list)
    preserved_justification_refs: list[str] = field(default_factory=list)
    required_approval_roles: list[str] = field(default_factory=list)
    failure_codes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.source_version, ScenarioVersion):
            raise ValueError("source_version must be a ScenarioVersion")
        require_non_empty(self.proposal_id, "proposal_id")
        require_non_empty(self.evaluation_id, "evaluation_id")
        if self.reaction_kind not in REACTION_KINDS:
            raise ValueError(f"reaction_kind must be one of {REACTION_KINDS}")
        if self.target_label not in BUSINESS_SCENARIO_LABELS:
            raise ValueError(f"target_label must be one of {BUSINESS_SCENARIO_LABELS}")
        require_non_empty(self.comparison_outcome, "comparison_outcome")
        require_non_empty(self.target_title, "target_title")
        require_strings(self.candidate_categories, "candidate_categories")
        require_strings(self.ranking_focus_areas, "ranking_focus_areas")
        require_strings(self.preserved_comparable_refs, "preserved_comparable_refs")
        require_strings(
            self.preserved_justification_refs,
            "preserved_justification_refs",
        )
        require_strings(self.required_approval_roles, "required_approval_roles")
        require_strings(self.failure_codes, "failure_codes")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["source_version"] = self.source_version.to_dict()
        return payload

    def build_candidate_version(
        self,
        *,
        version_id: str,
        saved_scenario_id: str,
        created_at: str,
        created_by: str = "policy-reactor",
    ) -> ScenarioVersion:
        require_non_empty(version_id, "version_id")
        require_non_empty(saved_scenario_id, "saved_scenario_id")
        require_non_empty(created_at, "created_at")
        require_non_empty(created_by, "created_by")

        snapshot_payload = self.source_version.snapshot_refs.to_dict()
        snapshot_notes = list(snapshot_payload.get("notes", []))
        snapshot_notes.extend(
            [
                f"policy-evaluation:{self.evaluation_id}",
                f"reaction-kind:{self.reaction_kind}",
            ]
        )
        if self.candidate_categories:
            snapshot_notes.append("candidate-categories:" + ",".join(self.candidate_categories))
        snapshot_payload["notes"] = _dedupe(snapshot_notes)

        version_notes = list(self.source_version.notes)
        version_notes.extend(self.notes)
        if self.failure_codes:
            version_notes.append("failure-codes:" + ",".join(self.failure_codes))

        version_tags = list(self.source_version.tags)
        version_tags.extend(["policy-reactive", self.reaction_kind, self.target_label])
        version_tags.extend(self.candidate_categories)

        return ScenarioVersion(
            version_id=version_id,
            saved_scenario_id=saved_scenario_id,
            trip_id=self.source_version.trip_id,
            title=self.target_title,
            label=self.target_label,
            created_at=created_at,
            created_by=created_by,
            scope=self.source_version.scope,
            based_on_version_id=self.source_version.version_id,
            snapshot_refs=ScenarioArtifactRefs.from_dict(snapshot_payload),
            summary=(f"Policy reaction {self.reaction_kind} for evaluation {self.evaluation_id}."),
            tags=sorted(set(version_tags)),
            notes=_dedupe(version_notes),
        )

    def build_comparison(
        self,
        *,
        comparison_id: str,
        candidate_scenario_id: str,
        compared_at: str,
    ) -> ScenarioComparison:
        require_non_empty(comparison_id, "comparison_id")
        require_non_empty(candidate_scenario_id, "candidate_scenario_id")
        require_non_empty(compared_at, "compared_at")

        focus_areas = _dedupe(self.ranking_focus_areas + self.candidate_categories)
        return ScenarioComparison(
            comparison_id=comparison_id,
            trip_id=self.source_version.trip_id,
            baseline_scenario_id=self.source_version.saved_scenario_id,
            candidate_scenario_id=candidate_scenario_id,
            compared_at=compared_at,
            outcome=self.comparison_outcome,
            summary=self.target_title,
            focus_areas=focus_areas,
            notes=_dedupe(self.notes),
        )


class ReoptimizationPlanningError(ValueError):
    """Raised when policy reoptimization planning inputs are inconsistent."""


class TPPReoptimizationService:
    """Build deterministic planner actions from policy-evaluation outputs."""

    def plan_reoptimization(
        self,
        proposal: TripPlanProposal,
        evaluation_result: PolicyEvaluationResult,
        context: PolicyReoptimizationContext,
    ) -> PolicyReoptimizationPlan:
        if not isinstance(proposal, TripPlanProposal):
            raise ReoptimizationPlanningError("proposal must be a TripPlanProposal")
        if not isinstance(evaluation_result, PolicyEvaluationResult):
            raise ReoptimizationPlanningError("evaluation_result must be a PolicyEvaluationResult")
        if not isinstance(context, PolicyReoptimizationContext):
            raise ReoptimizationPlanningError("context must be a PolicyReoptimizationContext")
        if evaluation_result.proposal_id != proposal.proposal_id:
            raise ReoptimizationPlanningError(
                "evaluation_result.proposal_id must match proposal.proposal_id"
            )
        if context.source_version.trip_id != proposal.trip_id:
            raise ReoptimizationPlanningError(
                "context.source_version.trip_id must match proposal.trip_id"
            )

        failure_categories = [
            item.related_category
            for item in evaluation_result.failure_reasons
            if item.related_category
        ]
        alternative_categories = [
            item.category for item in evaluation_result.preferred_alternatives
        ]
        candidate_categories = _dedupe(failure_categories + alternative_categories)
        if not candidate_categories:
            candidate_categories = _dedupe(
                list(context.comparable_refs) + list(context.justification_refs)
            )

        preserved_comparable_refs = _dedupe(
            [
                ref
                for category in candidate_categories
                for ref in context.comparable_refs.get(category, [])
            ]
        )
        preserved_comparable_refs = _dedupe(
            preserved_comparable_refs
            + [
                item.comparable_ref
                for item in evaluation_result.preferred_alternatives
                if item.comparable_ref and item.category in candidate_categories
            ]
        )
        preserved_justification_refs = _dedupe(
            [
                ref
                for category in candidate_categories
                for ref in context.justification_refs.get(category, [])
            ]
        )
        required_approval_roles = _dedupe(
            [item.role for item in evaluation_result.approval_requirements]
        )
        failure_codes = _dedupe([item.code for item in evaluation_result.failure_reasons])
        note_lines = list(evaluation_result.notes)
        note_lines.extend(evaluation_result.exception_guidance)
        note_lines.extend(item.message for item in evaluation_result.failure_reasons)

        reaction_kind = "rerank"
        target_label = "compliant_first"
        comparison_outcome = "preferred"
        target_title = "Policy-guided rerank of the current compliant scenario"
        ranking_focus_areas = list(candidate_categories)

        if evaluation_result.status == "exception_required":
            reaction_kind = "create_exception_candidate"
            target_label = "exception_nearest"
            comparison_outcome = "tradeoff"
            target_title = "Generate an exception-ready candidate scenario"
            ranking_focus_areas = _dedupe(candidate_categories + ["exception_handling", "approval"])
        elif evaluation_result.preferred_alternatives:
            reaction_kind = "narrow_candidates"
            comparison_outcome = "preferred"
            target_title = "Narrow candidate search around policy-preferred alternatives"
            ranking_focus_areas = _dedupe(
                candidate_categories + ["policy_alignment", "comparables"]
            )
        elif any(item.severity == "blocking" for item in evaluation_result.failure_reasons):
            reaction_kind = "regenerate_scenario"
            comparison_outcome = "tradeoff"
            target_title = "Regenerate a compliant scenario for fixable policy failures"
            ranking_focus_areas = _dedupe(
                candidate_categories + ["policy_alignment", "schedule_protection"]
            )
        elif evaluation_result.status == "non_compliant":
            reaction_kind = "manual_review"
            comparison_outcome = "tradeoff"
            target_title = "Route ambiguous non-compliant results into manual review"
            ranking_focus_areas = _dedupe(candidate_categories + ["policy_alignment"])

        if reaction_kind == "create_exception_candidate" and not preserved_justification_refs:
            note_lines.append(
                "Preserve planner justification context before requesting approval escalation."
            )

        return PolicyReoptimizationPlan(
            source_version=context.source_version,
            proposal_id=proposal.proposal_id,
            evaluation_id=evaluation_result.evaluation_id,
            reaction_kind=reaction_kind,
            target_label=target_label,
            comparison_outcome=comparison_outcome,
            target_title=target_title,
            candidate_categories=candidate_categories,
            ranking_focus_areas=ranking_focus_areas,
            preserved_comparable_refs=preserved_comparable_refs,
            preserved_justification_refs=preserved_justification_refs,
            required_approval_roles=required_approval_roles,
            failure_codes=failure_codes,
            notes=_dedupe(note_lines),
        )
