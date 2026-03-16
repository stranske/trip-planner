# Business Travel Profile

This document separates the business-travel model from the leisure preference engine.

The business side should reuse shared travel infrastructure where that makes sense, but it should not be treated as leisure planning with a few extra constraints.

## Purpose

`BusinessTravelProfile` should support a different planning objective:

- produce a realistic, approval-ready business trip
- optimize against policy constraints early
- preserve documentation, comparables, and booking-channel requirements

## Why Separate It

The leisure model is primarily about:

- personal tradeoffs
- exploratory travel shape
- discovery and pacing
- revealed preference over quality and experience

The business model is primarily about:

- trip purpose and necessity
- schedule rigidity
- policy fit
- approved channels
- comparables
- justification and documentation

Some fields overlap, but the center of gravity is different enough that the contract should be separate.

## BusinessTravelProfile Outline

```json
{
  "schema_version": "0.1.0",
  "profile_kind": "business",
  "traveler_context": {},
  "trip_purpose": {},
  "policy_constraints": {},
  "vendor_constraints": {},
  "schedule_requirements": {},
  "cost_controls": {},
  "comfort_floors": {},
  "documentation_requirements": {},
  "approval_targets": {},
  "exception_strategy": {}
}
```

## 1. Traveler Context

```json
{
  "employee_type": "employee|contractor|guest",
  "traveler_experience": "frequent|occasional",
  "home_airport": "",
  "loyalty_programs": [],
  "mobility_or_access_needs": []
}
```

## 2. Trip Purpose

```json
{
  "purpose_type": "client_meeting|conference|internal_meeting|site_visit|training|other",
  "business_justification": "",
  "required_presence_windows": [],
  "trip_criticality": "low|medium|high"
}
```

## 3. Policy Constraints

```json
{
  "required_booking_channels": [],
  "airfare_rules": {},
  "lodging_rules": {},
  "ground_transport_rules": {},
  "per_diem_or_meal_rules": {},
  "approval_triggers": [],
  "documentation_rules": []
}
```

## 4. Vendor Constraints

```json
{
  "preferred_vendors": [],
  "approved_vendors": [],
  "disallowed_vendors": [],
  "comparison_requirements": {
    "airfare": 2,
    "lodging": 2,
    "car_rental": 1
  }
}
```

## 5. Schedule Requirements

```json
{
  "arrival_buffer_preference": "tight|moderate|conservative",
  "meeting_protection_priority": 0.95,
  "same_day_return_tolerance": 0.3,
  "red_eye_tolerance": 0.1
}
```

## 6. Cost Controls

```json
{
  "overall_cost_priority": 0.8,
  "policy_compliance_priority": 1.0,
  "employee_convenience_priority": 0.6,
  "splurge_requires_justification": true
}
```

## 7. Comfort Floors

These are still important in business mode, but they are usually framed operationally rather than experientially.

Examples:

- quiet lodging near the meeting site
- arrival times that preserve readiness
- safe and reliable transport channels
- ability to work during transit

## 8. Documentation Requirements

```json
{
  "required_receipt_categories": [],
  "justification_fields": [],
  "comparable_capture_required": true,
  "booking_link_retention_required": true
}
```

## 9. Approval Targets

```json
{
  "needs_manager_approval": true,
  "needs_finance_review": false,
  "needs_exception_preclearance": true
}
```

## 10. Exception Strategy

The business planner should know what to do when no clean policy-conforming plan exists.

Examples:

- ask for additional comparables
- generate the nearest compliant alternative
- produce a documented exception candidate

## Contract With `Travel-Plan-Permission`

The cleanest integration model is:

1. `trip-planner` receives a `PolicyConstraintSet` or equivalent policy payload when available
2. `trip-planner` builds or updates `BusinessTravelProfile`
3. `trip-planner` generates a `TripPlanProposal`
4. `Travel-Plan-Permission` evaluates it and returns a `PolicyEvaluationResult`
5. `trip-planner` re-optimizes if the policy system identifies failures or preferred alternatives

This keeps planning and policy enforcement separate while still making policy optimization first-class.

## Planning Implications

Business planning should optimize earlier for:

- approved channels
- justification-ready choices
- comparable collection
- schedule protection
- policy-compliant or policy-nearest options

That is a different objective from leisure trip fit, even when the same inventory and mapping systems are used underneath.

## Immediate Next Design Step

Before opening a large business implementation backlog, the repo should define:

1. `BusinessTravelProfile`
2. `TripPlanProposal`
3. `PolicyConstraintSet`
4. `PolicyEvaluationResult`
5. the minimum fields needed for comparables and justification capture
