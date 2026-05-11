import { startTransition, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useLoaderData } from "react-router-dom";

import type { TripRecord } from "../api/trips";
import {
  answerPlannerDecision,
  createNotebookItem,
  deleteNotebookItem,
  fetchPlannerSession,
  recordWorkspaceSpendEvent,
  refreshWorkspaceProposalStatus,
  saveWorkspaceBudget,
  setNotebookFocus,
  submitPlannerTurn,
  submitRouteOptionAction,
  updateNotebookItem,
  updateWorkspacePlanningMode,
  type ActualSpendEventUpsertPayload,
  type BudgetPlanUpsertPayload,
  type BudgetWorkspaceState,
  type NotebookCategory,
  type NotebookPriority,
  type PlannerMessage,
  type PlannerSessionResponse,
  type PlannerStructuredBlock,
  type PlanningMode,
  type PlanningNotebookFocus,
  type PlanningNotebookItem,
  type PlanningNotebookState,
  type RouteOptionActionType,
  type RuntimeScenarioComparison,
  submitPlannerOptionFeedback,
  type SavedScenarioRecord,
  type WorkspaceData,
} from "../api/workspace";
import { WorkspaceBudgetPanel } from "../components/budget/WorkspaceBudgetPanel";
import { TripMap } from "../components/maps/TripMap";
import type { MapViewScope } from "../components/maps/mapSurface";
import { PlanningModeSelector } from "../components/planner/PlanningModeSelector";
import { PlannerSidePanelSurface } from "../components/planner/PlannerSidePanelSurface";
import { TripComparison } from "../components/trips/TripComparison";
import { PlanningNotebookPanel } from "../components/workspace/PlanningNotebookPanel";
import { RouteOptionWorkbench } from "../components/workspace/RouteOptionWorkbench";
import { ScenarioComparison } from "../components/workspace/ScenarioComparison";
import { AsyncRouteContent } from "../lib/routes/AsyncRouteContent";

type LoaderData = {
  workspace: Promise<WorkspaceData>;
  trips?: Promise<TripRecord[]>;
};

type TimelineStop = {
  key: string;
  label: string;
  routeIndex: number;
  startDay: number;
  endDay: number;
};

type RouteSegmentFocus = {
  id: string;
  fromLabel: string;
  toLabel: string;
  fromIndex: number;
  toIndex: number;
  durationMinutes: number | null;
  confidence: "high" | "medium" | "low";
  unavailableReason: string | null;
};

type ScenarioReviewMetric = {
  label: string;
  value: string;
};

type WorkspacePanelVisibility = {
  showBudgetPanel: boolean;
  showPolicyPosture: boolean;
  showProposalPanel: boolean;
  showApprovalReadinessPanel: boolean;
};

type PlannerPromptSuggestion = {
  label: string;
  draft: string;
};

type ProposalLifecycleState =
  | "pending"
  | "deferred"
  | "running"
  | "failed"
  | "completed-with-follow-up"
  | "approval-ready";

type ProposalLifecyclePresentation = {
  state: ProposalLifecycleState;
  readinessLabel: string;
  title: string;
  summary: string;
};

const PLANNER_PROMPT_SUGGESTIONS: PlannerPromptSuggestion[] = [
  {
    label: "Compare routes",
    draft: "Compare the strongest route options and tell me the main tradeoffs.",
  },
  {
    label: "Remember a note",
    draft: "Please remember this for later: ",
  },
  {
    label: "Revisit lodging",
    draft: "Revisit lodging options with budget, location, and transfer friction in mind.",
  },
  {
    label: "Summarize decisions",
    draft: "Summarize what we have decided, what is still open, and what you recommend next.",
  },
  {
    label: "Show rejected ideas",
    draft: "Show route or lodging ideas we considered and rejected, with the reason for each.",
  },
];

function formatDateRange(startDate: string | null, endDate: string | null): string {
  if (!startDate && !endDate) {
    return "Dates not set yet";
  }
  if (!startDate || !endDate) {
    const singleDate = startDate ?? endDate;
    return singleDate ? formatDate(singleDate) : "Dates not set yet";
  }
  return `${formatDate(startDate)} to ${formatDate(endDate)}`;
}

function titleCaseStop(stop: string): string {
  return stop
    .split(/[-_]/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function resolveActiveScenario(workspace: WorkspaceData) {
  const currentSavedScenarioId = workspace.session.current_saved_scenario_id;
  const savedScenario =
    workspace.saved_scenarios.find((scenario) => scenario.saved_scenario_id === currentSavedScenarioId) ??
    workspace.saved_scenarios[0];

  const activeVersion = savedScenario?.versions.find(
    (version) => version.version_id === savedScenario.current_version_id
  );
  const itineraryScenarioId = activeVersion?.snapshot_refs.itinerary_scenario_id;

  const matchedScenario = workspace.scenario_search.scenarios.find(
    (scenario) => scenario.scenario_id === itineraryScenarioId
  );

  return {
    savedScenario,
    activeVersion,
    scenario: matchedScenario ?? workspace.scenario_search.scenarios[0] ?? null,
  };
}

function resolveRouteComparison(workspace: WorkspaceData) {
  return workspace.route_comparison ?? workspace.runtime_scenario_comparison;
}

function resolveMapScenarioId(workspace: WorkspaceData): string | null {
  const activeScenario = resolveActiveScenario(workspace).scenario;
  if (activeScenario?.scenario_id) {
    return activeScenario.scenario_id;
  }
  return resolveRouteComparison(workspace).lead_scenario_id;
}

function buildTimelineStops(routeSequence: string[], tripDuration: number | null): TimelineStop[] {
  if (tripDuration == null || tripDuration <= 0 || routeSequence.length === 0) {
    return [];
  }
  const duration = tripDuration;

  const baseSpan = Math.floor(duration / routeSequence.length);
  let remainder = duration % routeSequence.length;
  let nextDay = 1;

  return routeSequence.map((stop, index) => {
    const span = Math.max(1, baseSpan + (remainder > 0 ? 1 : 0));
    remainder = Math.max(0, remainder - 1);
    const startDay = nextDay;
    const endDay = index === routeSequence.length - 1 ? duration : Math.min(duration, startDay + span - 1);
    nextDay = endDay + 1;

    return {
      key: `${stop}-${index}`,
      label: titleCaseStop(stop),
      routeIndex: index,
      startDay,
      endDay,
    };
  });
}

function fallbackSegmentId(scenarioId: string, routeSequence: string[], index: number): string {
  const fromStop = routeSequence[index];
  const toStop = routeSequence[index + 1];
  return `${scenarioId}-${fromStop}-${index}-${scenarioId}-${toStop}-${index + 1}`;
}

function routeSegmentFocusesFor(
  scenario: RuntimeScenarioComparison["scenarios"][number] | null
): RouteSegmentFocus[] {
  if (scenario == null) {
    return [];
  }

  const markers = scenario.map_view?.place_markers ?? [];
  const markerById = new Map(markers.map((marker) => [marker.id, marker]));
  const providerSegments = scenario.map_view?.rough_route_geometry ?? [];
  if (providerSegments.length > 0) {
    return providerSegments.map((segment, index) => {
      const fromMarker = markerById.get(segment.from_marker_id);
      const toMarker = markerById.get(segment.to_marker_id);
      return {
        id: segment.id,
        fromLabel: segment.from_label,
        toLabel: segment.to_label,
        fromIndex: fromMarker?.route_index ?? index,
        toIndex: toMarker?.route_index ?? index + 1,
        durationMinutes: segment.duration_minutes ?? null,
        confidence: segment.confidence ?? scenario.map_view?.confidence.level ?? "medium",
        unavailableReason: segment.unavailable_reason ?? null,
      };
    });
  }

  return scenario.route_sequence.slice(0, -1).map((fromStop, index) => ({
    id: fallbackSegmentId(scenario.scenario_id, scenario.route_sequence, index),
    fromLabel: titleCaseStop(fromStop),
    toLabel: titleCaseStop(scenario.route_sequence[index + 1]),
    fromIndex: index,
    toIndex: index + 1,
    durationMinutes:
      scenario.route_sequence.length > 1
        ? Math.max(0, Math.round(scenario.metrics.travel_minutes / (scenario.route_sequence.length - 1)))
        : null,
    confidence: scenario.feasible ? "medium" : "low",
    unavailableReason:
      "Provider distance is not available; duration is estimated from ranked scenario timing.",
  }));
}

function resolveRouteSegmentFocus(
  scenario: RuntimeScenarioComparison["scenarios"][number] | null,
  selectedSegmentId: string | null
): RouteSegmentFocus | null {
  const segments = routeSegmentFocusesFor(scenario);
  if (segments.length === 0) {
    return null;
  }
  return segments.find((segment) => segment.id === selectedSegmentId) ?? segments[0];
}

function timelineFocusNotes(
  ledger: WorkspaceData["planning_ledger"] | undefined,
  scenario: RuntimeScenarioComparison["scenarios"][number] | null,
  segment: RouteSegmentFocus | null
): string[] {
  const entries = ledger?.entries ?? [];
  if (entries.length === 0 || scenario == null) {
    return [];
  }
  const routeIds = new Set(
    [scenario.scenario_id, scenario.route_option_id, segment?.id].filter(
      (value): value is string => Boolean(value)
    )
  );
  return entries
    .filter((entry) => entry.status !== "superseded")
    .filter((entry) => {
      const metadata = entry.metadata ?? {};
      const refs = [
        entry.related_option_id,
        entry.related_decision_id,
        ...entry.source_refs,
        metadata["route_option_id"],
        metadata["scenario_id"],
        metadata["route_segment_id"],
        metadata["map_segment_id"],
        metadata["selected_segment_id"],
      ];
      return refs.some((ref) => typeof ref === "string" && routeIds.has(ref));
    })
    .map((entry) => entry.summary.trim())
    .filter(Boolean)
    .slice(0, 3);
}

function useCompactWorkspaceLayout(): boolean {
  const [isCompact, setIsCompact] = useState(() =>
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function"
      ? window.matchMedia("(max-width: 820px)").matches
      : false
  );

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }

    const mediaQuery = window.matchMedia("(max-width: 820px)");
    const updateLayout = (event: MediaQueryListEvent | MediaQueryList) => {
      setIsCompact(event.matches);
    };

    updateLayout(mediaQuery);

    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", updateLayout);
      return () => mediaQuery.removeEventListener("change", updateLayout);
    }

    mediaQuery.addListener(updateLayout);
    return () => mediaQuery.removeListener(updateLayout);
  }, []);

  return isCompact;
}

function formatDate(value: string): string {
  const dateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnlyMatch) {
    const [, year, month, day] = dateOnlyMatch;
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    }).format(new Date(Date.UTC(Number(year), Number(month) - 1, Number(day))));
  }

  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(value));
}

function formatCurrency(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 0,
    }).format(amount);
  }
}

function formatScenarioScore(score: number): string {
  return `${Math.round(score * 100)} / 100`;
}

function formatPolicyPosture(workspace: WorkspaceData): string {
  const presentation = workspace.view_model?.policy_presentation;
  if (presentation?.active_policy_state && presentation.posture_label) {
    return presentation.posture_label;
  }

  const proposalState = workspace.proposal_state;
  if (proposalState == null) {
    return "No approval packet yet";
  }

  if (proposalState.summary.approval_ready) {
    return "Approval-ready";
  }

  if (proposalState.summary.follow_up_status) {
    return formatFollowUpStatus(proposalState.summary.follow_up_status);
  }

  return proposalState.summary.evaluation_result_status ?? "review pending";
}

function hasActivePolicyState(proposalState: WorkspaceData["proposal_state"]): boolean {
  if (proposalState == null) {
    return false;
  }

  if (proposalState.execution_id) {
    return true;
  }

  if (proposalState.summary.approval_ready) {
    return true;
  }

  if (proposalState.summary.evaluation_result_status || proposalState.summary.follow_up_status) {
    return true;
  }

  return proposalState.submission_status !== "pending" || proposalState.evaluation_status != null;
}

function deriveWorkspacePanelVisibility(workspace: WorkspaceData): WorkspacePanelVisibility {
  const viewModelVisibility = workspace.view_model?.panel_visibility;
  if (viewModelVisibility) {
    return {
      showBudgetPanel: viewModelVisibility.show_budget_panel,
      showPolicyPosture: viewModelVisibility.show_policy_posture,
      showProposalPanel: viewModelVisibility.show_proposal_panel,
      showApprovalReadinessPanel: viewModelVisibility.show_approval_readiness_panel,
    };
  }

  const isBusinessTrip = workspace.trip_record.trip.mode === "business";
  const activePolicyState = hasActivePolicyState(workspace.proposal_state);
  const showPolicyPanels = isBusinessTrip || activePolicyState;

  return {
    showBudgetPanel: true,
    showPolicyPosture: showPolicyPanels,
    showProposalPanel: showPolicyPanels,
    showApprovalReadinessPanel: showPolicyPanels,
  };
}

function buildScenarioReviewMetrics(
  workspace: WorkspaceData,
  scenario: WorkspaceData["route_comparison"]["scenarios"][number],
  panelVisibility: WorkspacePanelVisibility
): ScenarioReviewMetric[] {
  const metrics: ScenarioReviewMetric[] = [
    {
      label: "Estimated total",
      value:
        scenario.metrics.estimated_total == null
          ? "Pending"
          : formatCurrency(
              scenario.metrics.estimated_total.typical_amount,
              scenario.metrics.estimated_total.currency
            ),
    },
    {
      label: "Travel minutes",
      value: `${scenario.metrics.travel_minutes} min`,
    },
    {
      label: "Transfers",
      value: `${scenario.metrics.transfers}`,
    },
    {
      label: "Feasibility",
      value: scenario.feasible ? "Ready to review" : "Needs feasibility work",
    },
  ];

  if (panelVisibility.showPolicyPosture) {
    metrics.push({
      label: "Approval posture",
      value: formatPolicyPosture(workspace),
    });
  }

  return metrics;
}

function ScenarioSummaryCard({
  savedScenario,
  activeVersion,
  isActive,
}: {
  savedScenario: SavedScenarioRecord;
  activeVersion: SavedScenarioRecord["versions"][number] | undefined;
  isActive: boolean;
}) {
  return (
    <article className={`scenario-card${isActive ? " scenario-card-active" : ""}`}>
      <p className="scenario-kicker">{activeVersion?.label ?? "saved"}</p>
      <h3>{activeVersion?.title ?? savedScenario.saved_scenario_id}</h3>
      <p>{activeVersion?.summary ?? "No saved summary yet."}</p>
    </article>
  );
}

function formatFollowUpStatus(status: string | undefined): string {
  if (!status) {
    return "pending";
  }
  return status.replace(/_/g, " ");
}

function isFailedLifecycleStatus(status: string | null | undefined): boolean {
  return status != null && ["failed", "error", "errored", "rejected", "invalid"].includes(status);
}

function isRunningLifecycleStatus(status: string | null | undefined): boolean {
  return (
    status != null &&
    ["submitted", "queued", "running", "in_progress", "processing"].includes(status)
  );
}

function shouldShowProposalRefresh(
  proposalState: NonNullable<WorkspaceData["proposal_state"]>,
  followUp: NonNullable<WorkspaceData["proposal_state"]>["follow_up"]
): boolean {
  const submissionStatus = proposalState.summary.submission_status ?? proposalState.submission_status;
  const evaluationTransportStatus =
    proposalState.summary.evaluation_transport_status ?? proposalState.evaluation_status;
  const awaitingEvaluation =
    proposalState.summary.evaluation_result_status == null &&
    (followUp?.status === "awaiting_evaluation" ||
      proposalState.summary.follow_up_status === "awaiting_evaluation" ||
      submissionStatus === "succeeded" ||
      evaluationTransportStatus === "succeeded");
  return Boolean(
    proposalState.summary.submission_requires_polling ||
      awaitingEvaluation
  );
}

function deriveProposalLifecyclePresentation(
  proposalState: NonNullable<WorkspaceData["proposal_state"]>,
  followUp: NonNullable<WorkspaceData["proposal_state"]>["follow_up"]
): ProposalLifecyclePresentation {
  const summary = proposalState.summary;
  const submissionStatus = summary.submission_status ?? proposalState.submission_status;
  const evaluationTransportStatus =
    summary.evaluation_transport_status ?? proposalState.evaluation_status;
  const followUpStatus = followUp?.status ?? summary.follow_up_status;
  const awaitingEvaluation =
    summary.evaluation_result_status == null &&
    (followUpStatus === "awaiting_evaluation" ||
      submissionStatus === "succeeded" ||
      evaluationTransportStatus === "succeeded");

  if (summary.approval_ready || followUpStatus === "resolved") {
    return {
      state: "approval-ready",
      readinessLabel: "Ready for approval",
      title: "Approval packet is ready",
      summary:
        summary.follow_up_summary ??
        summary.submission_summary ??
        "Policy evaluation passed and the workspace is ready for approval handling.",
    };
  }

  if (isFailedLifecycleStatus(submissionStatus) || isFailedLifecycleStatus(evaluationTransportStatus)) {
    return {
      state: "failed",
      readinessLabel: "Needs policy retry",
      title: "Live policy execution needs attention",
      summary:
        summary.submission_summary ??
        "The proposal could not complete a live policy run. Review the transport failure before retrying.",
    };
  }

  if (
    summary.evaluation_result_status != null ||
    (followUpStatus != null && followUpStatus !== "awaiting_evaluation")
  ) {
    const needsException =
      followUpStatus === "exception_required" ||
      followUpStatus === "exception_requested" ||
      followUpStatus === "reoptimization_required" ||
      summary.evaluation_result_status === "non_compliant";
    return {
      state: "completed-with-follow-up",
      readinessLabel: needsException ? "Needs exception" : "Needs follow-up",
      title: "Policy review finished with follow-up",
      summary:
        summary.follow_up_summary ??
        "The live policy run completed and the workspace now needs remediation or exception handling.",
    };
  }

  if (submissionStatus === "deferred" || evaluationTransportStatus === "deferred") {
    return {
      state: "deferred",
      readinessLabel: "Waiting for policy review",
      title: "Policy review is deferred",
      summary:
        summary.submission_summary ??
        "The remote policy service accepted the proposal and deferred the final verdict.",
    };
  }

  if (
    awaitingEvaluation ||
    summary.submission_requires_polling ||
    isRunningLifecycleStatus(submissionStatus) ||
    isRunningLifecycleStatus(evaluationTransportStatus)
  ) {
    return {
      state: "running",
      readinessLabel: "Waiting for policy review",
      title: awaitingEvaluation ? "Awaiting policy evaluation result" : "Policy review is running",
      summary:
        summary.follow_up_summary ??
        summary.submission_summary ??
        "The workspace is waiting for the latest remote policy execution result.",
    };
  }

  return {
    state: "pending",
    readinessLabel: "Waiting for policy review",
    title: "Approval packet is pending",
    summary: "Build and submit the approval packet to start live policy execution for this workspace.",
  };
}

function hasRenderableFollowUp(
  followUp: NonNullable<WorkspaceData["proposal_state"]>["follow_up"]
): followUp is NonNullable<NonNullable<WorkspaceData["proposal_state"]>["follow_up"]> {
  return Boolean(followUp?.status && followUp?.title && followUp?.summary);
}

function rebuildNotebookState(
  notebook: PlanningNotebookState,
  items: PlanningNotebookItem[]
): PlanningNotebookState {
  const activeItems = items.filter((i) => i.status === "active");
  const completedItems = items.filter((i) => i.status === "completed");
  const byCategory: Record<string, PlanningNotebookItem[]> = {};
  for (const item of activeItems) {
    (byCategory[item.category] ??= []).push(item);
  }
  return {
    ...notebook,
    items,
    summary: {
      total_count: items.length,
      active_count: activeItems.length,
      completed_count: completedItems.length,
      active_items: activeItems,
      completed_items: completedItems,
      by_category: byCategory,
    },
  };
}

function mergeWorkspaceBudgetState(
  workspace: WorkspaceData,
  budgetState: BudgetWorkspaceState
): WorkspaceData {
  const budgetPlanId = budgetState.budget_plan?.budget_plan_id ?? null;

  return {
    ...workspace,
    budget_state: budgetState,
    trip_record: {
      ...workspace.trip_record,
      artifact_refs: {
        ...workspace.trip_record.artifact_refs,
        budget_state_id: budgetPlanId,
      },
    },
    session: {
      ...workspace.session,
      active_budget_plan_id: budgetPlanId,
    },
  };
}

function mergePlannerSessionState(
  workspace: WorkspaceData,
  plannerSession: PlannerSessionResponse
): WorkspaceData {
  const plannerActivityIds = new Set(
    plannerSession.activity_log.map((entry) => entry.activity_event_id)
  );
  const sessionIncludesWorkspaceActivity = workspace.activity_log.every((entry) =>
    plannerActivityIds.has(entry.activity_event_id)
  );

  return {
    ...workspace,
    session: plannerSession.session,
    planner_panel_state: sessionIncludesWorkspaceActivity
      ? plannerSession.planner_panel_state
      : workspace.planner_panel_state,
    planner_memory: sessionIncludesWorkspaceActivity
      ? plannerSession.planner_memory
      : workspace.planner_memory,
    activity_log: sessionIncludesWorkspaceActivity
      ? plannerSession.activity_log
      : workspace.activity_log,
  };
}

const hiddenPlannerBlockKinds = new Set(["debug", "tool_call", "tool_trace", "diagnostic"]);

function legacyStructuredBlocks(message: PlannerMessage): PlannerStructuredBlock[] {
  return (
    message.turn_metadata?.visible_response_blocks.map((block) => ({
      kind: block.kind,
      title: block.title,
      body: "",
      items: block.items,
      metadata: {},
      hidden: false,
    })) ?? []
  );
}

function messageStructuredBlocks(message: PlannerMessage): PlannerStructuredBlock[] {
  return (message.structured_blocks ?? []).length > 0
    ? message.structured_blocks
    : legacyStructuredBlocks(message);
}

function isPlannerDiagnosticBlock(block: PlannerStructuredBlock): boolean {
  return block.hidden || hiddenPlannerBlockKinds.has(block.kind);
}

function plannerBlockKindLabel(kind: string): string {
  return kind.replace(/_/g, " ");
}

function PlannerStructuredBlockList({ blocks }: { blocks: PlannerStructuredBlock[] }) {
  if (blocks.length === 0) {
    return null;
  }

  return (
    <div className="planner-response-blocks">
      {blocks.map((block, blockIndex) => (
        <section
          key={`${block.kind}-${block.title}-${blockIndex}`}
          className={`planner-response-block planner-response-block-${block.kind}`}
        >
          <span className="planner-block-kind">{plannerBlockKindLabel(block.kind)}</span>
          <h4>{block.title}</h4>
          {block.body ? <p>{block.body}</p> : null}
          {block.items.length > 0 ? (
            <ul>
              {block.items.map((item, itemIndex) => (
                <li key={`${block.kind}-${block.title}-${itemIndex}`}>{item}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ))}
    </div>
  );
}

function PlannerMessageDiagnostics({
  message,
  blocks,
}: {
  message: PlannerMessage;
  blocks: PlannerStructuredBlock[];
}) {
  if (blocks.length === 0 && message.tool_calls.length === 0) {
    return null;
  }

  return (
    <div className="planner-diagnostics">
      {blocks.map((block, blockIndex) => (
        <details key={`${message.message_id}-${block.kind}-${blockIndex}`}>
          <summary>{block.title}</summary>
          {block.body ? <p>{block.body}</p> : null}
          {block.items.length > 0 ? (
            <ul>
              {block.items.map((item, itemIndex) => (
                <li key={`${message.message_id}-${block.kind}-${itemIndex}`}>{item}</li>
              ))}
            </ul>
          ) : null}
          {Object.keys(block.metadata).length > 0 ? (
            <pre>{JSON.stringify(block.metadata, null, 2)}</pre>
          ) : null}
        </details>
      ))}
      {message.tool_calls.length > 0 ? (
        <details>
          <summary>Tool calls</summary>
          <ul className="planner-tool-call-list">
            {message.tool_calls.map((toolCall, toolCallIndex) => (
              <li key={`${message.message_id}-${toolCall.tool_name}-${toolCallIndex}`}>
                {toolCall.tool_name}: {toolCall.summary}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function PlannerConversationMessage({
  message,
  showDiagnostics,
}: {
  message: PlannerMessage;
  showDiagnostics: boolean;
}) {
  const blocks = messageStructuredBlocks(message);
  const visibleBlocks = blocks.filter((block) => !isPlannerDiagnosticBlock(block));
  const diagnosticBlocks = blocks.filter(isPlannerDiagnosticBlock);

  return (
    <article className={`planner-message planner-message-${message.role}`}>
      <p className="scenario-kicker">{message.role === "user" ? "Traveler" : "Planner"}</p>
      <p>{message.content}</p>
      {message.turn_metadata?.plan_maturity ? (
        <span className="planner-routing-pill">
          {message.turn_metadata.plan_maturity.replace(/_/g, " ")}
        </span>
      ) : null}
      <PlannerStructuredBlockList blocks={visibleBlocks} />
      {showDiagnostics ? (
        <PlannerMessageDiagnostics message={message} blocks={diagnosticBlocks} />
      ) : null}
    </article>
  );
}

function PlanningLedgerPanel({
  ledger,
}: {
  ledger: WorkspaceData["planning_ledger"] | undefined;
}) {
  const resolvedLedger = ledger ?? {
    entries: [],
    summary: {
      active_decisions: [],
      open_questions: [],
      active_options: [],
      rejected_options: [],
      constraints: [],
      assumptions: [],
      source_references: [],
    },
  };
  const summaryGroups = [
    { label: "Decisions", entries: resolvedLedger.summary.active_decisions },
    { label: "Open questions", entries: resolvedLedger.summary.open_questions },
    { label: "Active options", entries: resolvedLedger.summary.active_options },
    { label: "Rejected options", entries: resolvedLedger.summary.rejected_options },
    { label: "Constraints", entries: resolvedLedger.summary.constraints },
    { label: "Assumptions", entries: resolvedLedger.summary.assumptions },
    { label: "Sources", entries: resolvedLedger.summary.source_references },
  ].filter((group) => group.entries.length > 0);

  return (
    <section className="status-card planning-ledger-card" aria-label="Planning ledger">
      <p className="status-label">Ledger</p>
      <h2>Planning ledger</h2>
      {resolvedLedger.entries.length === 0 ? (
        <p className="muted-copy">
          Decisions, questions, constraints, and route option history will appear here.
        </p>
      ) : (
        <div className="planning-ledger-grid">
          {summaryGroups.map((group) => (
            <section key={group.label} className="planning-ledger-group">
              <h3>{group.label}</h3>
              <ul>
                {group.entries.slice(0, 4).map((entry) => (
                  <li key={entry.ledger_entry_id}>
                    <span>{entry.summary}</span>
                    <small>{entry.status.replace("_", " ")}</small>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}

export function WorkspacePage() {
  const { workspace, trips } = useLoaderData() as LoaderData;
  const resolve = useMemo(
    () => Promise.all([workspace, trips ?? Promise.resolve([] as TripRecord[])]),
    [workspace, trips]
  );

  return (
    <AsyncRouteContent
      resolve={resolve}
      loading={{
        label: "Workspace",
        title: "Opening your trip workspace",
        message: "Loading the latest route ideas, notes, budget, and planning state.",
      }}
      error={{
        label: "Workspace",
        title: "Trip workspace could not load",
        message: "Refresh the page or try again after the latest trip data is available.",
      }}
    >
      {([resolvedWorkspace, resolvedTrips]) => (
        <WorkspacePageContent workspace={resolvedWorkspace} trips={resolvedTrips} />
      )}
    </AsyncRouteContent>
  );
}

function WorkspacePageContent({
  workspace,
  trips,
}: {
  workspace: WorkspaceData;
  trips: TripRecord[];
}) {
  const [currentWorkspace, setCurrentWorkspace] = useState(workspace);
  const [selectedScenarioId, setSelectedScenarioId] = useState(() =>
    resolveMapScenarioId(workspace)
  );
  const [selectedMapScope, setSelectedMapScope] = useState<MapViewScope>("regional");
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);
  const [selectedTripComparisonId, setSelectedTripComparisonId] = useState<string | null>(
    () => trips.find((trip) => trip.trip_id !== workspace.trip_record.trip.trip_id)?.trip_id ?? null
  );
  const [plannerSession, setPlannerSession] = useState<PlannerSessionResponse | null>(null);
  const [plannerConversationDraft, setPlannerConversationDraft] = useState("");
  const [plannerConversationError, setPlannerConversationError] = useState<string | null>(null);
  const [plannerConversationBusyLabel, setPlannerConversationBusyLabel] = useState<string | null>(
    null
  );
  const [showPlannerDiagnostics, setShowPlannerDiagnostics] = useState(false);
  const [plannerError, setPlannerError] = useState<string | null>(null);
  const [plannerBusyLabel, setPlannerBusyLabel] = useState<string | null>(null);
  const [planningModeBusy, setPlanningModeBusy] = useState(false);
  const [planningModeError, setPlanningModeError] = useState<string | null>(null);
  const [showWorkspaceDebugDetails, setShowWorkspaceDebugDetails] = useState(false);
  const [budgetError, setBudgetError] = useState<string | null>(null);
  const [budgetBusyLabel, setBudgetBusyLabel] = useState<string | null>(null);
  const [notebookError, setNotebookError] = useState<string | null>(null);
  const [notebookBusyLabel, setNotebookBusyLabel] = useState<string | null>(null);
  const [proposalError, setProposalError] = useState<string | null>(null);
  const [proposalBusyLabel, setProposalBusyLabel] = useState<string | null>(null);
  const [routeOptionError, setRouteOptionError] = useState<string | null>(null);
  const [routeOptionBusyLabel, setRouteOptionBusyLabel] = useState<string | null>(null);
  const plannerSessionLoadVersion = useRef(0);
  const isCompactLayout = useCompactWorkspaceLayout();
  useEffect(() => {
    setCurrentWorkspace(workspace);
    setSelectedScenarioId(resolveMapScenarioId(workspace));
    setSelectedMapScope("regional");
    setSelectedSegmentId(null);
    setShowWorkspaceDebugDetails(false);
  }, [workspace]);

  useEffect(() => {
    setSelectedTripComparisonId(
      trips.find((trip) => trip.trip_id !== workspace.trip_record.trip.trip_id)?.trip_id ?? null
    );
  }, [trips, workspace]);

  useEffect(() => {
    let isCancelled = false;
    plannerSessionLoadVersion.current += 1;
    const loadVersion = plannerSessionLoadVersion.current;
    setPlannerSession(null);
    setPlannerConversationError(null);
    setPlannerConversationBusyLabel("Loading planner conversation...");

    fetchPlannerSession(workspace.trip_record.trip.trip_id)
      .then((nextPlannerSession) => {
        if (isCancelled || plannerSessionLoadVersion.current !== loadVersion) {
          return;
        }
        startTransition(() => {
          setPlannerSession(nextPlannerSession);
          setCurrentWorkspace((current) => {
            if (
              current.session === nextPlannerSession.session &&
              current.planner_panel_state === nextPlannerSession.planner_panel_state &&
              current.planner_memory === nextPlannerSession.planner_memory &&
              current.activity_log === nextPlannerSession.activity_log
            ) {
              return current;
            }
            return mergePlannerSessionState(current, nextPlannerSession);
          });
        });
      })
      .catch((error) => {
        if (isCancelled || plannerSessionLoadVersion.current !== loadVersion) {
          return;
        }
        setPlannerConversationError(
          error instanceof Error ? error.message : "Planner conversation load failed."
        );
      })
      .finally(() => {
        if (!isCancelled && plannerSessionLoadVersion.current === loadVersion) {
          setPlannerConversationBusyLabel(null);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [workspace.trip_record.trip.trip_id]);

  const { trip } = currentWorkspace.trip_record;
  const productView = currentWorkspace.view_model;
  const activeScenario = resolveActiveScenario(currentWorkspace);
  const routeComparison = resolveRouteComparison(currentWorkspace);
  const selectedRuntimeScenario =
    routeComparison.scenarios.find(
      (scenario) => scenario.scenario_id === (selectedScenarioId ?? activeScenario.scenario?.scenario_id)
    ) ??
    routeComparison.scenarios[0] ??
    null;
  const timelineRouteSequence =
    selectedRuntimeScenario?.route_sequence ??
    activeScenario.scenario?.scenario_summary.route_sequence ??
    [];
  const timelineStops = buildTimelineStops(timelineRouteSequence, trip.trip_frame.duration_days);
  const selectedRouteSegment = resolveRouteSegmentFocus(selectedRuntimeScenario, selectedSegmentId);
  const selectedTimelineNotes = timelineFocusNotes(
    currentWorkspace.planning_ledger,
    selectedRuntimeScenario,
    selectedRouteSegment
  );
  const proposalFollowUp = currentWorkspace.proposal_state?.follow_up ?? null;
  const renderableProposalFollowUp = hasRenderableFollowUp(proposalFollowUp)
    ? proposalFollowUp
    : null;
  const proposalLifecycle =
    currentWorkspace.proposal_state == null
      ? null
      : deriveProposalLifecyclePresentation(
          currentWorkspace.proposal_state,
          renderableProposalFollowUp
        );
  const scenarioPolicyPosture = formatPolicyPosture(currentWorkspace);
  const panelVisibility = deriveWorkspacePanelVisibility(currentWorkspace);
  const workspaceDebugSections = useMemo(() => {
    const sections = { ...(productView?.debug_state.sections ?? {}) };
    if (currentWorkspace.proposal_state != null) {
      sections.proposal_state = {
        title: "Proposal diagnostics",
        payload: currentWorkspace.proposal_state,
      };
    }
    return sections;
  }, [productView?.debug_state.sections, currentWorkspace.proposal_state]);
  const workspaceDebugDisclosureKey = [
    trip.trip_id,
    currentWorkspace.proposal_state?.proposal_state_id ?? "no-proposal",
    Object.keys(workspaceDebugSections).sort().join("|"),
  ].join(":");
  function handleScenarioSelection(scenarioId: string) {
    setSelectedScenarioId(scenarioId);
    setSelectedSegmentId(null);
  }

  async function handlePlanningModeChange(mode: PlanningMode) {
    if (mode === currentWorkspace.session.selected_planning_mode) {
      return;
    }
    setPlanningModeError(null);
    setPlanningModeBusy(true);
    plannerSessionLoadVersion.current += 1;
    try {
      const nextWorkspace = await updateWorkspacePlanningMode(trip.trip_id, mode);
      setCurrentWorkspace(nextWorkspace);
    } catch (error) {
      setPlanningModeError(error instanceof Error ? error.message : "Planning mode update failed.");
    } finally {
      setPlanningModeBusy(false);
    }
  }

  async function handleDecisionAnswer(decisionId: string, choice: string) {
    setPlannerError(null);
    setPlannerBusyLabel("Saving planner decision...");
    plannerSessionLoadVersion.current += 1;
    try {
      const nextWorkspace = await answerPlannerDecision(trip.trip_id, decisionId, choice);
      setCurrentWorkspace(nextWorkspace);
    } catch (error) {
      setPlannerError(error instanceof Error ? error.message : "Planner decision update failed.");
    } finally {
      setPlannerBusyLabel(null);
    }
  }

  async function handleOptionFeedback(
    optionId: string,
    actionType: string,
    decisionId: string | null
  ) {
    setPlannerError(null);
    setPlannerBusyLabel("Saving planner feedback...");
    plannerSessionLoadVersion.current += 1;
    try {
      const nextWorkspace = await submitPlannerOptionFeedback(
        trip.trip_id,
        optionId,
        actionType as
          | "accept"
          | "reject"
          | "revise"
          | "save_as_fallback"
          | "do_more_before_asking_again",
        decisionId
      );
      setCurrentWorkspace(nextWorkspace);
    } catch (error) {
      setPlannerError(error instanceof Error ? error.message : "Planner feedback update failed.");
    } finally {
      setPlannerBusyLabel(null);
    }
  }

  async function handleRouteOptionAction(optionId: string, actionType: RouteOptionActionType) {
    setRouteOptionError(null);
    setRouteOptionBusyLabel("Saving route option...");
    plannerSessionLoadVersion.current += 1;
    try {
      const nextWorkspace = await submitRouteOptionAction(trip.trip_id, optionId, actionType);
      startTransition(() => {
        setCurrentWorkspace(nextWorkspace);
        setSelectedScenarioId(resolveMapScenarioId(nextWorkspace));
      });
    } catch (error) {
      setRouteOptionError(error instanceof Error ? error.message : "Route option update failed.");
    } finally {
      setRouteOptionBusyLabel(null);
    }
  }

  async function handlePlannerTurnSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = plannerConversationDraft.trim();
    if (!message) {
      setPlannerConversationError("Enter a planner message before sending a turn.");
      return;
    }

    setPlannerConversationError(null);
    setPlannerConversationBusyLabel("Sending planner turn...");
    plannerSessionLoadVersion.current += 1;
    try {
      const nextPlannerSession = await submitPlannerTurn(trip.trip_id, message);
      startTransition(() => {
        setPlannerSession(nextPlannerSession);
        setCurrentWorkspace((current) => mergePlannerSessionState(current, nextPlannerSession));
        setPlannerConversationDraft("");
      });
    } catch (error) {
      setPlannerConversationError(
        error instanceof Error ? error.message : "Planner conversation turn failed."
      );
    } finally {
      setPlannerConversationBusyLabel(null);
    }
  }

  function handlePlannerPromptSuggestion(draft: string) {
    setPlannerConversationDraft(draft);
    setPlannerConversationError(null);
  }

  async function handleBudgetSave(payload: BudgetPlanUpsertPayload) {
    setBudgetError(null);
    setBudgetBusyLabel("Saving workspace budget...");
    try {
      const nextBudgetState = await saveWorkspaceBudget(trip.trip_id, payload);
      startTransition(() => {
        setCurrentWorkspace((current) => mergeWorkspaceBudgetState(current, nextBudgetState));
      });
    } catch (error) {
      setBudgetError(error instanceof Error ? error.message : "Budget plan update failed.");
    } finally {
      setBudgetBusyLabel(null);
    }
  }

  async function handleSpendRecord(payload: ActualSpendEventUpsertPayload) {
    setBudgetError(null);
    setBudgetBusyLabel("Recording actual spend...");
    try {
      const nextBudgetState = await recordWorkspaceSpendEvent(trip.trip_id, payload);
      startTransition(() => {
        setCurrentWorkspace((current) => mergeWorkspaceBudgetState(current, nextBudgetState));
      });
    } catch (error) {
      setBudgetError(error instanceof Error ? error.message : "Spend entry failed.");
    } finally {
      setBudgetBusyLabel(null);
    }
  }

  function mergeNotebookItem(
    current: WorkspaceData,
    updatedItem: PlanningNotebookItem
  ): WorkspaceData {
    const notebook = current.planning_notebook;
    if (!notebook) {
      return current;
    }
    const items = notebook.items.map((item) =>
      item.notebook_item_id === updatedItem.notebook_item_id ? updatedItem : item
    );
    const existingIds = new Set(notebook.items.map((i) => i.notebook_item_id));
    if (!existingIds.has(updatedItem.notebook_item_id)) {
      items.push(updatedItem);
    }
    return { ...current, planning_notebook: rebuildNotebookState(notebook, items) };
  }

  function mergeNotebookItemDeleted(
    current: WorkspaceData,
    notebookItemId: string
  ): WorkspaceData {
    const notebook = current.planning_notebook;
    if (!notebook) {
      return current;
    }
    const items = notebook.items.filter((item) => item.notebook_item_id !== notebookItemId);
    const nextFocus: PlanningNotebookFocus = {
      category: notebook.focus.category,
      notebook_item_id:
        notebook.focus.notebook_item_id === notebookItemId
          ? null
          : notebook.focus.notebook_item_id,
    };
    return {
      ...current,
      planning_notebook: { ...rebuildNotebookState(notebook, items), focus: nextFocus },
    };
  }

  function mergeNotebookFocus(
    current: WorkspaceData,
    nextFocus: PlanningNotebookFocus
  ): WorkspaceData {
    const notebook = current.planning_notebook;
    if (!notebook) {
      return current;
    }
    return { ...current, planning_notebook: { ...notebook, focus: nextFocus } };
  }

  async function handleNotebookCreate(payload: {
    title: string;
    category: NotebookCategory;
    note?: string;
    priority?: NotebookPriority;
  }) {
    setNotebookError(null);
    setNotebookBusyLabel("Adding notebook item...");
    try {
      const newItem = await createNotebookItem(trip.trip_id, payload);
      startTransition(() => {
        setCurrentWorkspace((current) => mergeNotebookItem(current, newItem));
      });
    } catch (error) {
      setNotebookError(error instanceof Error ? error.message : "Notebook item creation failed.");
    } finally {
      setNotebookBusyLabel(null);
    }
  }

  async function handleNotebookComplete(notebookItemId: string) {
    setNotebookError(null);
    try {
      const updatedItem = await updateNotebookItem(trip.trip_id, notebookItemId, {
        status: "completed",
      });
      startTransition(() => {
        setCurrentWorkspace((current) => mergeNotebookItem(current, updatedItem));
      });
    } catch (error) {
      setNotebookError(error instanceof Error ? error.message : "Notebook item update failed.");
    }
  }

  async function handleNotebookReopen(notebookItemId: string) {
    setNotebookError(null);
    try {
      const updatedItem = await updateNotebookItem(trip.trip_id, notebookItemId, {
        status: "active",
      });
      startTransition(() => {
        setCurrentWorkspace((current) => mergeNotebookItem(current, updatedItem));
      });
    } catch (error) {
      setNotebookError(error instanceof Error ? error.message : "Notebook item reopen failed.");
    }
  }

  async function handleNotebookDelete(notebookItemId: string) {
    setNotebookError(null);
    try {
      await deleteNotebookItem(trip.trip_id, notebookItemId);
      startTransition(() => {
        setCurrentWorkspace((current) => mergeNotebookItemDeleted(current, notebookItemId));
      });
    } catch (error) {
      setNotebookError(error instanceof Error ? error.message : "Notebook item deletion failed.");
    }
  }

  async function handleNotebookSetFocus(focus: {
    category?: NotebookCategory | null;
    notebook_item_id?: string | null;
  }) {
    setNotebookError(null);
    try {
      const nextFocus = await setNotebookFocus(trip.trip_id, focus);
      startTransition(() => {
        setCurrentWorkspace((current) => mergeNotebookFocus(current, nextFocus));
      });
    } catch (error) {
      setNotebookError(error instanceof Error ? error.message : "Notebook focus update failed.");
    }
  }

  async function handleProposalRefresh() {
    setProposalError(null);
    setProposalBusyLabel("Refreshing live policy status...");
    try {
      const nextProposalState = await refreshWorkspaceProposalStatus(trip.trip_id);
      startTransition(() => {
        setCurrentWorkspace((current) => ({
          ...current,
          proposal_state: nextProposalState,
        }));
      });
    } catch (error) {
      setProposalError(error instanceof Error ? error.message : "Proposal status refresh failed.");
    } finally {
      setProposalBusyLabel(null);
    }
  }

  return (
    <section
      className={`workspace-layout${isCompactLayout ? " workspace-layout-compact" : ""}`}
      data-layout={isCompactLayout ? "compact" : "full"}
    >
      <div className="workspace-hero status-card">
        <p className="status-label">
          {productView?.user_summary.mode_label ?? "Trip workspace"}
        </p>
        <h2>{productView?.user_summary.trip_title ?? trip.title}</h2>
        <p>{productView?.user_summary.headline ?? trip.summary}</p>
        {productView ? (
          <div className="decision-stack" aria-label="Product workspace summary">
            {productView.user_summary.decided.length > 0 ? (
              <article className="decision-card">
                <p className="scenario-kicker">Decided</p>
                <ul>
                  {productView.user_summary.decided.map((item, index) => (
                    <li key={`${index}-${item}`}>{item}</li>
                  ))}
                </ul>
              </article>
            ) : null}
            {productView.user_summary.uncertain.length > 0 ? (
              <article className="decision-card">
                <p className="scenario-kicker">Still open</p>
                <ul>
                  {productView.user_summary.uncertain.map((item, index) => (
                    <li key={`${index}-${item}`}>{item}</li>
                  ))}
                </ul>
              </article>
            ) : null}
            <article className="decision-card">
              <p className="scenario-kicker">Next action</p>
              <h3>{productView.next_step.title}</h3>
              <p>{productView.next_step.summary}</p>
              {productView.next_step.action_label ? (
                <p className="muted-copy">{productView.next_step.action_label}</p>
              ) : null}
            </article>
            {productView.business_summary ? (
              <article className="decision-card">
                <p className="scenario-kicker">Approval readiness</p>
                <h3>{productView.business_summary.headline}</h3>
                {productView.business_summary.blockers.length > 0 ? (
                  <ul>
                    {productView.business_summary.blockers.map((blocker, index) => (
                      <li key={`${index}-${blocker}`}>{blocker}</li>
                    ))}
                  </ul>
                ) : null}
              </article>
            ) : null}
          </div>
        ) : null}
        <dl className="workspace-meta">
          <div>
            <dt>Dates</dt>
            <dd>{formatDateRange(trip.trip_frame.start_date, trip.trip_frame.end_date)}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>
              {trip.trip_frame.duration_days == null
                ? "Duration not set yet"
                : `${trip.trip_frame.duration_days} days`}
            </dd>
          </div>
          <div>
            <dt>Mode</dt>
            <dd>{trip.mode}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{trip.status}</dd>
          </div>
        </dl>
        <p className="workspace-hero-emphasis">
          {isCompactLayout
            ? "Compact review keeps route, day plan, and next choices close together."
            : "Use this trip workspace to compare options, capture traveler notes, and move toward one clear next step."}
        </p>
        <details className="workspace-help-disclosure">
          <summary>How to use this trip workspace</summary>
          <div className="workspace-help-grid">
            <article>
              <h3>Check the next decision</h3>
              <p>Start with trip status and open choices, then ask your planner for the next action to take.</p>
            </article>
            <article>
              <h3>Compare options</h3>
              <p>Use the map, route tradeoffs, day plan, and saved ideas to compare what fits this traveler goal.</p>
            </article>
            <article>
              <h3>Capture reminders</h3>
              <p>Send reminders to your planner so they stay with this trip and can be pulled into the next revision.</p>
            </article>
          </div>
        </details>
        {Object.keys(workspaceDebugSections).length > 0 ? (
          <details
            key={workspaceDebugDisclosureKey}
            className="workspace-debug-disclosure"
            open={showWorkspaceDebugDetails}
            onToggle={(event) => setShowWorkspaceDebugDetails(event.currentTarget.open)}
          >
            <summary>Advanced diagnostics</summary>
            <p className="muted-copy">
              {Object.keys(workspaceDebugSections).length} debug section
              {Object.keys(workspaceDebugSections).length === 1 ? "" : "s"} available for
              troubleshooting.
            </p>
            {showWorkspaceDebugDetails ? (
              <div className="workspace-debug-section-list">
                {Object.entries(workspaceDebugSections).map(([sectionId, section]) => (
                  <article key={sectionId} className="workspace-debug-section">
                    <h3>{section.title}</h3>
                    <pre>{JSON.stringify(section.payload, null, 2)}</pre>
                  </article>
                ))}
              </div>
            ) : null}
          </details>
        ) : null}
      </div>

      <div className="workspace-grid">
        <section className="status-card planner-panel-card">
          <p className="status-label">Planner</p>
          <h2>Traveler planning workspace</h2>
          <p className="muted-copy">
            Use your planner to compare options, keep context, and decide the next best trip step.
          </p>
          <div className="planner-runtime-row" aria-label="Planner availability">
            <span
              className={`planner-runtime-pill planner-runtime-pill--${
                currentWorkspace.planner_panel_state.planner_behavior.runtime_status ?? "fallback"
              }`}
            >
              {currentWorkspace.planner_panel_state.planner_behavior.runtime_mode === "model"
                ? "AI-assisted planner"
                : "Guided planner"}
            </span>
            <span className="planner-runtime-mode">
              {currentWorkspace.planner_panel_state.planner_behavior.runtime_mode === "model"
                ? "Live assistance"
                : "Planning guide"}
            </span>
          </div>
          {selectedRuntimeScenario ? (
            <article className="planner-route-focus" aria-label="Planner route focus">
              <p className="scenario-kicker">Route focus</p>
              <h3>{selectedRuntimeScenario.title}</h3>
              <p>
                {selectedRouteSegment
                  ? `${selectedRouteSegment.fromLabel} to ${selectedRouteSegment.toLabel}`
                  : selectedRuntimeScenario.route_summary}
              </p>
              {selectedTimelineNotes.length > 0 ? (
                <ul>
                  {selectedTimelineNotes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : null}
            </article>
          ) : null}
          <PlanningModeSelector
            value={currentWorkspace.session.selected_planning_mode}
            busy={planningModeBusy}
            error={planningModeError}
            onChange={handlePlanningModeChange}
          />
          {plannerBusyLabel ? <p className="muted-copy">{plannerBusyLabel}</p> : null}
          {plannerError ? <p className="planner-inline-error">{plannerError}</p> : null}
          <PlannerSidePanelSurface
            key={currentWorkspace.planner_panel_state === workspace.planner_panel_state ? "loader" : "workspace"}
            state={currentWorkspace.planner_panel_state}
            onDecisionAnswer={handleDecisionAnswer}
            onOptionFeedback={handleOptionFeedback}
          />
          <section className="planner-conversation-card" aria-label="Planner conversation">
            <div className="planner-conversation-header">
              <div>
                <p className="scenario-kicker">Conversation</p>
                <h3>Message your planner</h3>
                <p>
                  Ask for comparisons, summaries, reminders, or a specific next step. The answer
                  stays with this trip.
                </p>
              </div>
              <div className="planner-conversation-actions">
                <span className="planner-conversation-pill">
                  {plannerSession?.messages.length ?? 0} message
                  {(plannerSession?.messages.length ?? 0) === 1 ? "" : "s"}
                </span>
                <button
                  type="button"
                  className="planner-diagnostics-toggle"
                  aria-pressed={showPlannerDiagnostics}
                  onClick={() => setShowPlannerDiagnostics((current) => !current)}
                >
                  Diagnostics
                </button>
              </div>
            </div>
            {plannerConversationBusyLabel ? (
              <p className="muted-copy">{plannerConversationBusyLabel}</p>
            ) : null}
            {plannerConversationError ? (
              <p className="planner-inline-error">{plannerConversationError}</p>
            ) : null}
            <div className="planner-message-list" aria-live="polite">
              {plannerSession == null || plannerSession.messages.length === 0 ? (
                <article className="planner-message planner-message-empty">
                  <p>
                    No planner conversation yet. Send a message to start shaping this trip.
                  </p>
                </article>
              ) : (
                plannerSession.messages.map((message) => (
                  <PlannerConversationMessage
                    key={message.message_id}
                    message={message}
                    showDiagnostics={showPlannerDiagnostics}
                  />
                ))
              )}
            </div>
            <div className="planner-prompt-suggestions" aria-label="Planner prompt suggestions">
              {PLANNER_PROMPT_SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion.label}
                  type="button"
                  onClick={() => handlePlannerPromptSuggestion(suggestion.draft)}
                >
                  {suggestion.label}
                </button>
              ))}
            </div>
            <form className="planner-conversation-form" onSubmit={handlePlannerTurnSubmit}>
              <label>
                Message the planner
                <textarea
                  value={plannerConversationDraft}
                  onChange={(event) => setPlannerConversationDraft(event.target.value)}
                  placeholder="Ask what to compare, what to remember, or what decision comes next."
                  rows={3}
                />
              </label>
              <button type="submit" disabled={Boolean(plannerConversationBusyLabel)}>
                Send message
              </button>
            </form>
          </section>
        </section>

        {panelVisibility.showBudgetPanel ? (
          <WorkspaceBudgetPanel
            budgetState={currentWorkspace.budget_state}
            tripMode={trip.mode}
            busyLabel={budgetBusyLabel}
            errorMessage={budgetError}
            onSaveBudget={handleBudgetSave}
            onRecordSpend={handleSpendRecord}
          />
        ) : null}

        <TripMap
          comparison={routeComparison}
          scenarioComparisonSummary={currentWorkspace.scenario_comparison?.summary}
          scenarioFocusAreas={currentWorkspace.scenario_comparison?.focus_areas ?? []}
          activeScenarioId={selectedScenarioId}
          onSelectScenario={handleScenarioSelection}
          bundles={currentWorkspace.inventory_summary.bundles}
          feasibilitySummary={currentWorkspace.feasibility_summary}
          tripPrimaryRegions={trip.trip_frame.primary_regions}
          tripMode={trip.mode}
          policyPosture={panelVisibility.showPolicyPosture ? scenarioPolicyPosture : null}
          planningLedger={currentWorkspace.planning_ledger}
          activeScope={selectedMapScope}
          selectedSegmentId={selectedRouteSegment?.id ?? null}
          onScopeChange={setSelectedMapScope}
          onSelectSegment={setSelectedSegmentId}
          compactLayout={isCompactLayout}
        />

        <ScenarioComparison
          comparison={routeComparison}
          savedScenarios={currentWorkspace.saved_scenarios}
          selectedScenarioId={selectedScenarioId}
          onSelectScenario={handleScenarioSelection}
        />

        <RouteOptionWorkbench
          comparison={routeComparison}
          selectedScenarioId={selectedScenarioId}
          busyLabel={routeOptionBusyLabel}
          errorMessage={routeOptionError}
          onSelectScenario={handleScenarioSelection}
          onRouteOptionAction={handleRouteOptionAction}
        />

        <PlanningLedgerPanel ledger={currentWorkspace.planning_ledger} />

        {currentWorkspace.planning_notebook ? (
          <PlanningNotebookPanel
            notebookState={currentWorkspace.planning_notebook}
            busyLabel={notebookBusyLabel}
            errorMessage={notebookError}
            onCreateItem={handleNotebookCreate}
            onCompleteItem={handleNotebookComplete}
            onReopenItem={handleNotebookReopen}
            onDeleteItem={handleNotebookDelete}
            onSetFocus={handleNotebookSetFocus}
          />
        ) : null}

        <TripComparison
          currentTrip={currentWorkspace.trip_record.trip}
          trips={trips}
          selectedTripId={selectedTripComparisonId}
          onSelectTrip={setSelectedTripComparisonId}
        />

        {panelVisibility.showApprovalReadinessPanel ? (
          <section className="status-card" data-testid="approval-packet">
            <p className="status-label">Approval packet</p>
            <h2 data-testid="proposal-lifecycle">
              {proposalLifecycle?.title ?? "Proposal lifecycle in progress"}
            </h2>
          {currentWorkspace.proposal_state == null ? (
            <p className="muted-copy">
              Approval packet records have not been saved for this workspace yet.
            </p>
          ) : (
            <>
              {proposalBusyLabel ? <p className="muted-copy">{proposalBusyLabel}</p> : null}
              {proposalError ? <p className="planner-inline-error">{proposalError}</p> : null}
              <dl className="workspace-meta">
                <div>
                  <dt>Approval readiness</dt>
                  <dd>
                    {currentWorkspace.view_model?.policy_presentation.approval_status_label ??
                      proposalLifecycle?.readinessLabel ??
                      "Waiting for policy review"}
                  </dd>
                </div>
                <div>
                  <dt>Packet status</dt>
                  <dd>{currentWorkspace.proposal_state.summary.submission_status ?? "unknown"}</dd>
                </div>
                <div>
                  <dt>Comparables</dt>
                  <dd>{currentWorkspace.proposal_state.summary.comparable_count ?? 0}</dd>
                </div>
                <div>
                  <dt>Next step</dt>
                  <dd>
                    {currentWorkspace.view_model?.policy_presentation.next_step_label ??
                      formatFollowUpStatus(
                        renderableProposalFollowUp?.status ??
                          currentWorkspace.proposal_state.summary.follow_up_status
                      )}
                  </dd>
                </div>
              </dl>
              <p>{proposalLifecycle?.summary ?? "Submission stored for later review."}</p>
              {shouldShowProposalRefresh(
                currentWorkspace.proposal_state,
                renderableProposalFollowUp
              ) ? (
                <button type="button" className="secondary-button" onClick={handleProposalRefresh}>
                  Refresh live status
                </button>
              ) : null}
              {renderableProposalFollowUp ? (
                <article className="decision-card">
                  <h3>{renderableProposalFollowUp.recommended_label ?? renderableProposalFollowUp.title}</h3>
                  <p>{renderableProposalFollowUp.summary}</p>
                  {renderableProposalFollowUp.guidance &&
                  renderableProposalFollowUp.guidance.length > 0 ? (
                    <p className="muted-copy">{renderableProposalFollowUp.guidance[0]}</p>
                  ) : null}
                </article>
              ) : proposalLifecycle?.state === "running" || proposalLifecycle?.state === "deferred" ? (
                <article className="decision-card">
                  <h3>Keep the workspace open for remote results</h3>
                  <p>
                    Reloading the workspace preserves the latest stored execution state, so you can safely return
                    after the remote policy service posts a new verdict.
                  </p>
                </article>
              ) : proposalLifecycle?.state === "failed" ? (
                <article className="decision-card">
                  <h3>Review the live transport failure</h3>
                  <p>
                    Validate the remote TPP configuration and retry posture before asking travelers to treat this
                    workspace as approval-ready.
                  </p>
                </article>
              ) : null}
              <div className="decision-stack">
                {(currentWorkspace.proposal_state.summary.highlights ?? []).map((highlight) => (
                  <article key={highlight} className="decision-card">
                    <p>{highlight}</p>
                  </article>
                ))}
              </div>
            </>
          )}
          </section>
        ) : null}

        <section className="status-card">
          <p className="status-label">Things to consider</p>
          <h2>
            {workspace.inventory_summary.bundle_count > 0
              ? "Places and options to review"
              : "Options need more trip detail"}
          </h2>
          <p>
            {workspace.inventory_summary.bundle_count > 0
              ? "Grouped lodging, transport, and activity ideas are ready to inspect."
              : "Add dates, trip length, or route direction so the planner can group useful options."}
          </p>
          <p className="muted-copy">{workspace.inventory_summary.notes[0]}</p>
          {workspace.inventory_summary.bundle_count === 0 ? (
            <p className="muted-copy">
              {workspace.inventory_summary.runtime_state.status === "partial"
                ? "The planner needs a little more trip detail before it can group options."
                : "No option groups have been created for this trip yet."}
            </p>
          ) : (
            <div className="scenario-stack">
              {workspace.inventory_summary.bundles.map((bundle) => (
                <article key={bundle.bundle_id} className="scenario-card">
                  <p className="scenario-kicker">{bundle.bundle_context.replace(/_/g, " ")}</p>
                  <h3>{bundle.title}</h3>
                  <p>{bundle.summary}</p>
                  <p className="muted-copy">
                    {bundle.destination_names.join(" -> ")} · {bundle.option_count} normalized option
                    {bundle.option_count === 1 ? "" : "s"}
                  </p>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="status-card">
          <p className="status-label">Day plan</p>
          {timelineStops.length === 0 || activeScenario.scenario === null ? (
            <>
              <h2>Day plan is not ready yet</h2>
              <p>
                Choose or build a route idea before reviewing day-by-day pacing.
              </p>
              <p className="muted-copy">
                Ask the planner to compare routes or draft a first sequence of stops.
              </p>
            </>
          ) : (
            <>
              <h2>{isCompactLayout ? "Compact day-by-day review" : "Trip rhythm and day sequence"}</h2>
              <p>{selectedRuntimeScenario?.summary ?? activeScenario.scenario.scenario_summary.headline}</p>
              <div className="timeline-summary-grid" aria-label="Timeline summary">
                <article className="timeline-summary-card">
                  <p className="scenario-kicker">Duration</p>
                  <h3>
                    {trip.trip_frame.duration_days == null
                      ? "Trip length pending"
                      : `${trip.trip_frame.duration_days} days planned`}
                  </h3>
                  <p>Dates: {formatDateRange(trip.trip_frame.start_date, trip.trip_frame.end_date)}</p>
                </article>
                <article className="timeline-summary-card">
                  <p className="scenario-kicker">Route shape</p>
                  <h3>{timelineStops.length} review checkpoints</h3>
                  <p>
                    {selectedRuntimeScenario?.route_summary ??
                      activeScenario.scenario.scenario_summary.route_sequence.join(" -> ")}
                  </p>
                </article>
                <article className="timeline-summary-card">
                  <p className="scenario-kicker">Segment focus</p>
                  <h3>
                    {selectedRouteSegment
                      ? `${selectedRouteSegment.fromLabel} to ${selectedRouteSegment.toLabel}`
                      : "No segment selected"}
                  </h3>
                  <p>
                    {selectedRouteSegment?.durationMinutes != null
                      ? `${selectedRouteSegment.durationMinutes} minutes in the selected route option.`
                      : "Segment timing will appear when route geometry is available."}
                  </p>
                </article>
                <article className="timeline-summary-card">
                  <p className="scenario-kicker">Pacing</p>
                  <h3>
                    {selectedRuntimeScenario == null
                      ? "Planner score pending"
                      : `${formatScenarioScore(selectedRuntimeScenario.metrics.score)} planner score`}
                  </h3>
                  <p>
                    {panelVisibility.showPolicyPosture
                      ? `${scenarioPolicyPosture} approval posture for the current workspace.`
                      : "Pacing and route burden stay visible without approval details."}
                  </p>
                </article>
                <article className="timeline-summary-card">
                  <p className="scenario-kicker">Options</p>
                  <h3>
                    {selectedRuntimeScenario == null
                      ? "Option count pending"
                      : `${selectedRuntimeScenario.option_count} mapped options`}
                  </h3>
                  <p>
                    {selectedRuntimeScenario?.comparison_note ??
                      "Details update as route ideas become clearer."}
                  </p>
                </article>
              </div>
              {selectedTimelineNotes.length > 0 ? (
                <div className="timeline-focus-notes" aria-label="Timeline linked planning notes">
                  {selectedTimelineNotes.map((note) => (
                    <span key={note}>{note}</span>
                  ))}
                </div>
              ) : null}
              <ol className="timeline-list" aria-label="Trip timeline sequence">
                {timelineStops.map((stop) => {
                  const isSegmentFocus =
                    selectedRouteSegment != null &&
                    (stop.routeIndex === selectedRouteSegment.fromIndex ||
                      stop.routeIndex === selectedRouteSegment.toIndex);
                  return (
                  <li
                    key={stop.key}
                    className={`timeline-stop${isSegmentFocus ? " timeline-stop-focused" : ""}`}
                  >
                    <div className="timeline-dayband">
                      <span>Day {stop.startDay}</span>
                      <span>Day {stop.endDay}</span>
                    </div>
                    <div>
                      <h3>{stop.label}</h3>
                      <p>
                        Days {stop.startDay}-{stop.endDay} keep this stop visible in the selected
                        route review path.
                      </p>
                      {isSegmentFocus ? (
                        <p className="muted-copy">
                          Highlighted for the selected segment-level review.
                        </p>
                      ) : null}
                    </div>
                  </li>
                  );
                })}
              </ol>
            </>
          )}
        </section>

        <section className="status-card">
          <p className="status-label">Route tradeoffs</p>
          <h2>{isCompactLayout ? "Compact route tradeoffs" : "Review route tradeoffs"}</h2>
          <p>
            {panelVisibility.showPolicyPosture
              ? "Cost, route burden, feasibility, and approval posture stay scannable here without forcing you into raw planning notes."
              : "Cost, route burden, and feasibility stay scannable here without forcing you into raw planning notes."}
          </p>
          {routeComparison.scenarios.length > 0 ? (
            <div className="scenario-review-grid" aria-label="Scenario review board">
              {routeComparison.scenarios.map((scenario) => {
                const reviewMetrics = buildScenarioReviewMetrics(
                  currentWorkspace,
                  scenario,
                  panelVisibility
                );
                const isSelected = scenario.scenario_id === selectedScenarioId;

                return (
                  <article
                    key={scenario.scenario_id}
                    className={`scenario-card scenario-review-card${
                      isSelected ? " scenario-card-active" : ""
                    }`}
                    aria-label={`${scenario.title} review summary`}
                  >
                    <p className="scenario-kicker">
                      {scenario.recommended_for_selection ? "recommended" : scenario.status}
                    </p>
                    <h3>{scenario.title}</h3>
                    <p>{scenario.summary}</p>
                    <dl className="workspace-meta scenario-review-metrics">
                      {reviewMetrics.map((metric) => (
                        <div key={`${scenario.scenario_id}-${metric.label}`}>
                          <dt>{metric.label}</dt>
                          <dd
                            data-testid={
                              metric.label === "Approval posture" ? "policy-posture" : undefined
                            }
                          >
                            {metric.value}
                          </dd>
                        </div>
                      ))}
                    </dl>
                    <p className="muted-copy">{scenario.comparison_note}</p>
                    <ul className="focus-area-list scenario-highlight-list">
                      {scenario.highlights.slice(0, 2).map((highlight) => (
                        <li key={highlight}>{highlight}</li>
                      ))}
                    </ul>
                  </article>
                );
              })}
            </div>
          ) : (
            <p className="muted-copy">
              {currentWorkspace.runtime_state.status === "partial"
                ? "Add a little more trip detail before route comparison can start."
                : "No route ideas are available yet, so there is nothing to compare."}
            </p>
          )}
        </section>

        <section className="status-card">
          <p className="status-label">Saved ideas</p>
          <h2>{currentWorkspace.scenario_search.title}</h2>
          <div className="scenario-stack">
            {currentWorkspace.saved_scenarios.map((savedScenario) => {
              const activeVersion = savedScenario.versions.find(
                (version) => version.version_id === savedScenario.current_version_id
              );

              return (
                <ScenarioSummaryCard
                  key={savedScenario.saved_scenario_id}
                  savedScenario={savedScenario}
                  activeVersion={activeVersion}
                  isActive={
                    savedScenario.saved_scenario_id === currentWorkspace.session.current_saved_scenario_id
                  }
                />
              );
            })}
            {currentWorkspace.saved_scenarios.length === 0 ? (
              <p className="muted-copy">
                No saved route ideas exist yet. Ask the planner to compare routes or save a
                promising direction.
              </p>
            ) : null}
          </div>
        </section>
      </div>

      <div className="workspace-grid">
        <section className="status-card">
          <p className="status-label">Planning settings</p>
          <h2>Current collaboration style</h2>
          <dl className="workspace-meta">
            <div>
              <dt>Interaction</dt>
              <dd>{currentWorkspace.session.interaction_state.interaction_style}</dd>
            </div>
            <div>
              <dt>Initiative</dt>
              <dd>{currentWorkspace.session.interaction_state.initiative_level}</dd>
            </div>
            <div>
              <dt>Checkpointing</dt>
              <dd>{currentWorkspace.session.interaction_state.checkpoint_frequency}</dd>
            </div>
          </dl>
          <div className="decision-stack">
            {currentWorkspace.session.pending_decisions.length === 0 ? (
              <p className="muted-copy">No blocking decisions are waiting for you right now.</p>
            ) : (
              currentWorkspace.session.pending_decisions.map((decision) => (
                <article key={decision.decision_id} className="decision-card">
                  <h3>{decision.title}</h3>
                  <p>{decision.prompt}</p>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="status-card">
          <p className="status-label">Saved comparison</p>
          <h2>{currentWorkspace.scenario_comparison?.summary ?? "No comparison saved yet"}</h2>
          {currentWorkspace.scenario_comparison ? (
            <>
              <p>Outcome: {currentWorkspace.scenario_comparison.outcome}</p>
              <ul className="focus-area-list">
                {currentWorkspace.scenario_comparison.focus_areas.map((focusArea) => (
                  <li key={focusArea}>{focusArea.replace(/_/g, " ")}</li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted-copy">Saved route tradeoff comparisons will appear here.</p>
          )}
        </section>

        {panelVisibility.showProposalPanel ? (
          <section className="status-card" data-testid="tpp-label">
            <p className="status-label">Approval details</p>
            <h2>Options and readiness signals</h2>
          {currentWorkspace.proposal_state == null ? (
            <p className="muted-copy">Approval-packet details will render here once the packet is saved.</p>
          ) : (
            <div className="decision-stack">
              {renderableProposalFollowUp ? (
                <article className="decision-card">
                  <h3>{renderableProposalFollowUp.recommended_label ?? renderableProposalFollowUp.title}</h3>
                  <p>{renderableProposalFollowUp.summary}</p>
                  {renderableProposalFollowUp.selected_alternative?.summary ? (
                    <p className="muted-copy">
                      Selected alternative: {renderableProposalFollowUp.selected_alternative.summary}
                    </p>
                  ) : null}
                  {renderableProposalFollowUp.requested_exception?.reason ? (
                    <p className="muted-copy">
                      Exception rationale: {renderableProposalFollowUp.requested_exception.reason}
                    </p>
                  ) : null}
                </article>
              ) : null}
              {(renderableProposalFollowUp?.guidance ?? []).map((guidance) => (
                <article key={guidance} className="decision-card">
                  <h3>Guidance</h3>
                  <p>{guidance}</p>
                </article>
              ))}
              {(renderableProposalFollowUp?.alternatives ?? []).map((alternative) => (
                <article
                  key={`${alternative.category}-${alternative.summary}`}
                  className="decision-card"
                >
                  <h3>{alternative.summary}</h3>
                  <p>{alternative.rationale}</p>
                </article>
              ))}
            </div>
          )}
          </section>
        ) : null}

        <section className="status-card">
          <p className="status-label">Planning notes</p>
          <h2>
            {currentWorkspace.planner_memory.artifacts.length > 0
              ? "Planner notes to keep"
              : "No planner notes have been saved yet"}
          </h2>
          {currentWorkspace.planner_memory.artifacts.length === 0 ? (
            <p className="muted-copy">
              Important summaries and remembered decisions will appear here after the first planner
              conversation.
            </p>
          ) : (
            <div className="decision-stack">
              {currentWorkspace.planner_memory.artifacts.slice(0, 3).map((artifact) => (
                <article key={artifact.memory_artifact_id} className="decision-card">
                  <h3>{artifact.title}</h3>
                  <p>{artifact.summary}</p>
                  <p className="muted-copy">{artifact.detail}</p>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="status-card">
          <p className="status-label">Recent activity</p>
          <h2>Latest trip planning actions</h2>
          <div className="decision-stack">
            {currentWorkspace.activity_log.length === 0 ? (
              <p className="muted-copy">Planner actions will appear here after the first decision or feedback event.</p>
            ) : (
              currentWorkspace.activity_log.slice(0, 4).map((entry) => (
                <article key={entry.activity_event_id} className="decision-card">
                  <h3>{entry.event_kind.replace(/_/g, " ")}</h3>
                  <p>{entry.summary}</p>
                </article>
              ))
            )}
          </div>
        </section>
      </div>
    </section>
  );
}
