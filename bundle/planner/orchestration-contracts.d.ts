/**
 * Frontend declarations for orchestration-facing planner payloads.
 *
 * These interfaces mirror the canonical Python contracts used by the planner:
 * - trip_planner/contracts/trip.py
 * - trip_planner/contracts/options.py
 * - trip_planner/business/policy_contracts.py
 */

export interface TripFrameSummary {
  start_date: string | null;
  end_date: string | null;
  duration_days: number | null;
  primary_regions: string[];
  traveler_party: {
    kind: string;
    traveler_count: number;
    notes: string;
  };
}

export interface TripRecord {
  trip_id: string;
  user_id: string;
  mode: "leisure" | "business";
  status: "draft" | "active" | "booked" | "in_trip" | "completed" | "archived";
  trip_frame: TripFrameSummary;
  profile_refs: {
    leisure_profile_id?: string | null;
    business_profile_id?: string | null;
  };
  title: string;
  summary: string;
}

export interface OptionRecord {
  option_id: string;
  kind: string;
  label: string;
  summary: string;
  drawbacks: string[];
  explanation: string[];
}

export interface OptionAxisRecord {
  key: string;
  label: string;
  direction: string;
}

export interface OptionSetRecord {
  option_set_id: string;
  trip_id: string;
  purpose: string;
  scope: string;
  title: string;
  options: OptionRecord[];
  comparison_axes: OptionAxisRecord[];
  explanation: string[];
}

export interface PolicyApprovalRequirementRecord {
  role: string;
  reason: string;
  mandatory: boolean;
}

export interface PolicyFailureReasonRecord {
  code: string;
  message: string;
  severity: string;
  related_category: string;
}

export interface PreferredAlternativeRecord {
  category: string;
  summary: string;
  rationale: string;
  comparable_ref?: string | null;
}

export interface PolicyEvaluationRecord {
  evaluation_id: string;
  proposal_id: string;
  status: "compliant" | "non_compliant" | "exception_required";
  approval_requirements: PolicyApprovalRequirementRecord[];
  failure_reasons: PolicyFailureReasonRecord[];
  preferred_alternatives: PreferredAlternativeRecord[];
  exception_guidance: string[];
  notes: string[];
  compliance_score: number;
}

export interface ComparableCostRecord {
  currency: string;
  typical_amount: number;
}

export interface ComparableOptionRecord {
  category: string;
  label: string;
  vendor: string;
  booking_channel: string;
  estimated_cost: ComparableCostRecord;
  notes: string[];
}

export interface ProposalJustificationRecord {
  category: string;
  summary: string;
  evidence: string[];
}

export interface ProposalExceptionRequestRecord {
  exception_type: string;
  reason: string;
  requested_approval_roles: string[];
  notes: string[];
}

export interface ProposalRecord {
  proposal_id: string;
  comparables: ComparableOptionRecord[];
  justifications?: ProposalJustificationRecord[];
  approval_notes?: string[];
  requested_exception?: ProposalExceptionRequestRecord | null;
}

export interface PendingDecisionRecord {
  decision_id: string;
  title: string;
  prompt: string;
  choices: string[];
}

export interface PlannerOutputRecord {
  output_id: string;
  title: string;
  body: string;
  tags: string[];
  status?: "positive" | "caution" | "critical" | "neutral";
  highlights?: string[];
}

export interface PlannerBehaviorRecord {
  trip_stage: string;
  ask_before_next_major_change: boolean;
  target_research_passes: number;
  target_options_before_checkpoint: number;
  surface_options_early: boolean;
  explanation_density: "lean" | "standard" | "detailed";
}

export interface NextStepActionRecord {
  action_id: string;
  action_kind: "review_outputs" | "answer_decision" | "compare_options" | "prepare_approval";
  label: string;
  description: string;
  emphasis: "primary" | "secondary" | "quiet";
  target_section: "outputs" | "decisions" | "options" | "approval";
}

export interface PlannerPanelState {
  trip: TripRecord;
  option_set: OptionSetRecord;
  proposal: ProposalRecord | null;
  policy_evaluation: PolicyEvaluationRecord | null;
  pending_decisions: PendingDecisionRecord[];
  outputs: PlannerOutputRecord[];
  planner_behavior: PlannerBehaviorRecord;
  next_step_actions: NextStepActionRecord[];
}

export interface PlannerUiScenarioRecord {
  scenario_id: string;
  label: string;
  workflow: string;
  persona_summary: string;
  panel_state: PlannerPanelState;
}
