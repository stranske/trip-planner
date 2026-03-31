"""Deterministic business-planning objective derivation."""

from __future__ import annotations

from collections.abc import Iterable

from trip_planner.business.objectives import (
    BookingChannelObjectives,
    BusinessPlanningObjectives,
    ComparableRequirementObjectives,
    ComfortFloorObjectives,
    CostControlObjectives,
    ExceptionPathObjectives,
    JustificationReadinessObjectives,
    ObjectiveExplanationBundle,
    PlanningPathObjectives,
    ScheduleProtectionObjectives,
)
from trip_planner.business.policy_contracts import PolicyConstraintSet
from trip_planner.business.profile import BusinessTravelProfile


def _sorted_strings(values: Iterable[str]) -> list[str]:
    return sorted(values)


def _merge_unique(*groups: Iterable[str]) -> list[str]:
    return sorted({item for group in groups for item in group})


def _effective_required_channels(
    profile: BusinessTravelProfile,
    constraint_set: PolicyConstraintSet | None,
) -> list[str]:
    constraint_channels = constraint_set.required_booking_channels if constraint_set else []
    return _merge_unique(
        constraint_channels,
        profile.policy_constraints.required_booking_channels,
    )


def _effective_documentation_rules(
    profile: BusinessTravelProfile,
    constraint_set: PolicyConstraintSet | None,
) -> list[str]:
    constraint_rules = constraint_set.documentation_rules if constraint_set else []
    return _merge_unique(constraint_rules, profile.policy_constraints.documentation_rules)


def _effective_allowed_exception_types(
    constraint_set: PolicyConstraintSet | None,
) -> list[str]:
    if constraint_set is None:
        return []
    return _sorted_strings(constraint_set.allowed_exception_types)


def _channel_strategy(
    profile: BusinessTravelProfile,
    constraint_set: PolicyConstraintSet | None,
) -> BookingChannelObjectives:
    required_channels = _effective_required_channels(profile, constraint_set)
    if required_channels and profile.cost_controls.policy_compliance_priority >= 0.9:
        channel_mode = "approved_only"
    elif required_channels:
        channel_mode = "approved_first"
    else:
        channel_mode = "flexible"

    notes = []
    if required_channels:
        notes.append("Prioritize required booking channels before evaluating convenience.")
    if profile.vendor_constraints.approved_vendors:
        notes.append("Approved vendors remain preferred after channel compliance is satisfied.")
    if profile.vendor_constraints.disallowed_vendors:
        notes.append("Disallowed vendors should be excluded from option assembly.")
    return BookingChannelObjectives(
        required_channels=required_channels,
        channel_mode=channel_mode,
        notes=notes,
    )


def _schedule_protection(
    profile: BusinessTravelProfile,
) -> ScheduleProtectionObjectives:
    priority = profile.schedule_requirements.meeting_protection_priority
    arrival_buffer = profile.schedule_requirements.arrival_buffer_preference
    if profile.trip_purpose.trip_criticality == "high" and priority >= 0.95:
        protection_level = "mission_critical"
    elif priority >= 0.75 or arrival_buffer == "conservative":
        protection_level = "protected"
    else:
        protection_level = "standard"

    notes = [
        f"Trip criticality={profile.trip_purpose.trip_criticality}.",
        f"Required presence windows={len(profile.trip_purpose.required_presence_windows)}.",
    ]
    if profile.schedule_requirements.same_day_return_tolerance <= 0.25:
        notes.append("Avoid same-day return plans unless they clearly preserve readiness.")
    if profile.schedule_requirements.red_eye_tolerance == 0.0:
        notes.append("Red-eye options should not be preferred in default planning.")
    return ScheduleProtectionObjectives(
        protection_level=protection_level,
        arrival_buffer_preference=arrival_buffer,
        same_day_return_tolerance=profile.schedule_requirements.same_day_return_tolerance,
        red_eye_tolerance=profile.schedule_requirements.red_eye_tolerance,
        notes=notes,
    )


def _comparable_requirements(
    profile: BusinessTravelProfile,
    constraint_set: PolicyConstraintSet | None,
) -> ComparableRequirementObjectives:
    notes = []
    documentation_rules = _effective_documentation_rules(profile, constraint_set)
    if profile.documentation_requirements.comparable_capture_required:
        notes.append("Comparable capture is required before proposal export.")
    if documentation_rules:
        notes.append("Documentation rules: " + ", ".join(documentation_rules))
    return ComparableRequirementObjectives(
        required_categories={
            key: profile.vendor_constraints.comparison_requirements[key]
            for key in sorted(profile.vendor_constraints.comparison_requirements)
        },
        capture_required=profile.documentation_requirements.comparable_capture_required,
        additional_comparables_for_exception=(
            profile.exception_strategy.require_additional_comparables
        ),
        notes=notes,
    )


def _justification_readiness(
    profile: BusinessTravelProfile,
    constraint_set: PolicyConstraintSet | None,
) -> JustificationReadinessObjectives:
    required_fields = _sorted_strings(profile.documentation_requirements.justification_fields)
    if profile.approval_targets.needs_exception_preclearance:
        required_fields = _merge_unique(required_fields, ["exception rationale"])
    documentation_rules = _effective_documentation_rules(profile, constraint_set)
    notes = []
    if documentation_rules:
        notes.append("Carry policy documentation rules into proposal assembly.")
    if profile.documentation_requirements.booking_link_retention_required:
        notes.append("Retain booking links for later policy review and audit trails.")
    return JustificationReadinessObjectives(
        required_fields=required_fields,
        required_receipt_categories=_sorted_strings(
            profile.documentation_requirements.required_receipt_categories
        ),
        booking_link_retention_required=(
            profile.documentation_requirements.booking_link_retention_required
        ),
        maintain_exception_packet=(
            profile.approval_targets.needs_exception_preclearance
            or profile.exception_strategy.fallback_mode != "nearest_compliant"
        ),
        notes=notes,
    )


def _cost_control_posture(profile: BusinessTravelProfile) -> CostControlObjectives:
    overall = profile.cost_controls.overall_cost_priority
    compliance = profile.cost_controls.policy_compliance_priority
    convenience = profile.cost_controls.employee_convenience_priority
    if compliance >= max(overall, convenience) and compliance >= 0.85:
        posture = "policy_first"
    elif overall > max(compliance, convenience):
        posture = "cost_first"
    else:
        posture = "balanced"

    notes = []
    if profile.cost_controls.splurge_requires_justification:
        notes.append("Higher-comfort upgrades require explicit justification support.")
    if convenience >= 0.7:
        notes.append("Traveler convenience remains material once policy gates are satisfied.")
    return CostControlObjectives(
        posture=posture,
        overall_cost_priority=overall,
        policy_compliance_priority=compliance,
        employee_convenience_priority=convenience,
        notes=notes,
    )


def _comfort_floor(profile: BusinessTravelProfile) -> ComfortFloorObjectives:
    required_categories: list[str] = []
    if profile.comfort_floors.lodging_needs:
        required_categories.append("lodging")
    if profile.comfort_floors.transport_needs:
        required_categories.append("transport")
    if profile.comfort_floors.arrival_readiness_needs:
        required_categories.append("arrival_readiness")
    if profile.comfort_floors.work_enablers:
        required_categories.append("work_enablers")
    if profile.traveler_context.mobility_or_access_needs:
        required_categories.append("mobility")

    notes = []
    if profile.comfort_floors.arrival_readiness_needs:
        notes.append("Protect arrival-readiness needs before relaxing comfort floors.")
    if profile.traveler_context.mobility_or_access_needs:
        notes.append("Mobility or access needs must stay feasible in fallback plans.")
    return ComfortFloorObjectives(
        required_categories=sorted(required_categories),
        preserve_arrival_readiness=(
            bool(profile.comfort_floors.arrival_readiness_needs)
            or profile.schedule_requirements.arrival_buffer_preference == "conservative"
        ),
        notes=notes,
    )


def _exception_path(
    profile: BusinessTravelProfile,
    constraint_set: PolicyConstraintSet | None,
) -> ExceptionPathObjectives:
    allowed_exception_types = _effective_allowed_exception_types(constraint_set)
    fallback_mode = profile.exception_strategy.fallback_mode
    if (
        fallback_mode == "nearest_compliant"
        and not profile.approval_targets.needs_exception_preclearance
    ):
        posture = "compliant_first"
    elif fallback_mode == "manual_review":
        posture = "policy_nearest"
    else:
        posture = "exception_ready"

    notes = list(profile.exception_strategy.notes)
    if allowed_exception_types:
        notes.append("Allowed exception types: " + ", ".join(allowed_exception_types))
    if profile.exception_strategy.require_additional_comparables:
        notes.append("Prepare additional comparables before escalating exception paths.")
    return ExceptionPathObjectives(
        posture=posture,
        fallback_mode=fallback_mode,
        allowed_exception_types=allowed_exception_types,
        approval_roles=_sorted_strings(profile.approval_targets.approval_roles),
        preclearance_required=profile.approval_targets.needs_exception_preclearance,
        notes=notes,
    )


def _planning_paths(
    profile: BusinessTravelProfile,
    channel_strategy: BookingChannelObjectives,
    schedule_protection: ScheduleProtectionObjectives,
    comparable_requirements: ComparableRequirementObjectives,
    exception_path: ExceptionPathObjectives,
) -> tuple[PlanningPathObjectives, PlanningPathObjectives]:
    trigger_signals: list[str] = []
    if channel_strategy.channel_mode == "approved_only":
        trigger_signals.append("approved_only_channels")
    if schedule_protection.protection_level == "mission_critical":
        trigger_signals.append("mission_critical_schedule")
    if profile.approval_targets.needs_exception_preclearance:
        trigger_signals.append("exception_preclearance")
    if comparable_requirements.additional_comparables_for_exception:
        trigger_signals.append("additional_exception_comparables")
    if profile.traveler_context.mobility_or_access_needs:
        trigger_signals.append("mobility_or_access_needs")

    compliant_first = PlanningPathObjectives(
        mode="compliant_first",
        active=True,
        trigger_signals=[
            signal
            for signal in trigger_signals
            if signal in {"approved_only_channels", "mission_critical_schedule"}
        ],
        notes=[
            "Start with policy-compliant channels and vendors before relaxing tradeoffs.",
            "Preserve schedule protection and comfort floors inside compliant options first.",
        ],
    )
    fallback_active = exception_path.posture != "compliant_first" or bool(
        {
            "mission_critical_schedule",
            "exception_preclearance",
            "mobility_or_access_needs",
        }
        & set(trigger_signals)
    )
    policy_nearest = PlanningPathObjectives(
        mode="policy_nearest",
        active=fallback_active,
        trigger_signals=trigger_signals,
        notes=[
            "Use the nearest policy fit when a clean compliant plan may not preserve the trip objective.",
        ]
        + (
            ["Retain comparables and justification material so review can explain the fallback."]
            if fallback_active
            else []
        ),
    )
    return compliant_first, policy_nearest


def _build_explanations(
    profile: BusinessTravelProfile,
    constraint_set: PolicyConstraintSet | None,
    compliant_first_path: PlanningPathObjectives,
    policy_nearest_fallback: PlanningPathObjectives,
    channel_strategy: BookingChannelObjectives,
    schedule_protection: ScheduleProtectionObjectives,
    comparable_requirements: ComparableRequirementObjectives,
    justification_readiness: JustificationReadinessObjectives,
    cost_control_posture: CostControlObjectives,
    comfort_floor_protection: ComfortFloorObjectives,
    exception_path_posture: ExceptionPathObjectives,
) -> tuple[list[str], ObjectiveExplanationBundle]:
    required_channels = _effective_required_channels(profile, constraint_set)
    summary = [
        f"purpose:{profile.trip_purpose.purpose_type}",
        f"trip_criticality:{profile.trip_purpose.trip_criticality}",
        f"required_presence_windows:{len(profile.trip_purpose.required_presence_windows)}",
        (
            "meeting_protection_priority:"
            f"{profile.schedule_requirements.meeting_protection_priority:.2f}"
        ),
        "required_booking_channels:" + ",".join(required_channels or ["none"]),
        "comparison_requirements:"
        + ",".join(
            f"{key}={value}"
            for key, value in sorted(profile.vendor_constraints.comparison_requirements.items())
        ),
        "justification_fields:"
        + ",".join(
            _sorted_strings(profile.documentation_requirements.justification_fields) or ["none"]
        ),
        "approval_roles:"
        + ",".join(_sorted_strings(profile.approval_targets.approval_roles) or ["none"]),
        f"fallback_mode:{profile.exception_strategy.fallback_mode}",
        f"compliant_first_active:{str(compliant_first_path.active).lower()}",
        f"policy_nearest_fallback_active:{str(policy_nearest_fallback.active).lower()}",
    ]
    if constraint_set is not None:
        summary.append(f"policy_constraint_set:{constraint_set.policy_id}")
        summary.append(
            "allowed_exception_types:"
            + ",".join(_effective_allowed_exception_types(constraint_set) or ["none"])
        )
    category_reasons = {
        "planning_paths": [
            f"primary={compliant_first_path.mode}",
            f"fallback_active={str(policy_nearest_fallback.active).lower()}",
        ]
        + policy_nearest_fallback.trigger_signals,
        "channel_strategy": channel_strategy.notes
        + [f"channel_mode={channel_strategy.channel_mode}"],
        "schedule_protection": schedule_protection.notes
        + [f"protection_level={schedule_protection.protection_level}"],
        "comparable_requirements": comparable_requirements.notes
        + ["capture_required=" + str(comparable_requirements.capture_required).lower()],
        "justification_readiness": justification_readiness.notes
        + [
            "maintain_exception_packet="
            + str(justification_readiness.maintain_exception_packet).lower()
        ],
        "cost_control_posture": cost_control_posture.notes
        + [f"posture={cost_control_posture.posture}"],
        "comfort_floor_protection": comfort_floor_protection.notes
        + [
            "preserve_arrival_readiness="
            + str(comfort_floor_protection.preserve_arrival_readiness).lower()
        ],
        "exception_path_posture": exception_path_posture.notes
        + [f"posture={exception_path_posture.posture}"],
    }
    return summary, ObjectiveExplanationBundle(
        summary=summary,
        category_reasons=category_reasons,
    )


def derive_business_planning_objectives(
    profile: BusinessTravelProfile,
    trip_id: str,
    constraint_set: PolicyConstraintSet | None = None,
    objective_id: str | None = None,
) -> BusinessPlanningObjectives:
    """Derive deterministic business-planning objectives from policy-aware inputs."""
    channel_strategy = _channel_strategy(profile, constraint_set)
    schedule_protection = _schedule_protection(profile)
    comparable_requirements = _comparable_requirements(profile, constraint_set)
    justification_readiness = _justification_readiness(profile, constraint_set)
    cost_control_posture = _cost_control_posture(profile)
    comfort_floor_protection = _comfort_floor(profile)
    exception_path_posture = _exception_path(profile, constraint_set)
    compliant_first_path, policy_nearest_fallback = _planning_paths(
        profile,
        channel_strategy,
        schedule_protection,
        comparable_requirements,
        exception_path_posture,
    )
    explanations, explanation_bundle = _build_explanations(
        profile,
        constraint_set,
        compliant_first_path,
        policy_nearest_fallback,
        channel_strategy,
        schedule_protection,
        comparable_requirements,
        justification_readiness,
        cost_control_posture,
        comfort_floor_protection,
        exception_path_posture,
    )
    return BusinessPlanningObjectives(
        objective_id=objective_id or f"{trip_id}-business-objectives-v1",
        trip_id=trip_id,
        compliant_first_path=compliant_first_path,
        policy_nearest_fallback=policy_nearest_fallback,
        channel_strategy=channel_strategy,
        schedule_protection=schedule_protection,
        comparable_requirements=comparable_requirements,
        justification_readiness=justification_readiness,
        cost_control_posture=cost_control_posture,
        comfort_floor_protection=comfort_floor_protection,
        exception_path_posture=exception_path_posture,
        explanation_bundle=explanation_bundle,
        explanations=explanations,
    )
