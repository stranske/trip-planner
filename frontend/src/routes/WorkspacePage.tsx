import { startTransition, useEffect, useRef, useState, type FormEvent } from "react";
import { useLoaderData } from "react-router-dom";

import type { TripRecord } from "../api/trips";
import {
  answerPlannerDecision,
  fetchPlannerSession,
  recordWorkspaceSpendEvent,
  refreshWorkspaceProposalStatus,
  saveWorkspaceBudget,
  submitPlannerTurn,
  type ActualSpendEventUpsertPayload,
  type BudgetPlanUpsertPayload,
  type BudgetWorkspaceState,
  type PlannerSessionResponse,
  submitPlannerOptionFeedback,
  type SavedScenarioRecord,
  type WorkspaceData,
} from "../api/workspace";
import { WorkspaceBudgetPanel } from "../components/budget/WorkspaceBudgetPanel";
import { TripMap } from "../components/maps/TripMap";
import { PlannerSidePanelSurface } from "../components/planner/PlannerSidePanelSurface";
import { TripComparison } from "../components/trips/TripComparison";
import { ScenarioComparison } from "../components/workspace/ScenarioComparison";
import { AsyncRouteContent } from "../lib/routes/AsyncRouteContent";

type LoaderData = {
  workspace: Promise<WorkspaceData>;
  trips?: Promise<TripRecord[]>;
};

type TimelineStop = {
  key: string;
  label: string;
  startDay: number;
  endDay: number;
};

type ScenarioReviewMetric = {
  label: string;
  value: string;
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
  label: string;
  title: string;
  summary: string;
};

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

function resolveMapScenarioId(workspace: WorkspaceData): string | null {
  const activeScenario = resolveActiveScenario(workspace).scenario;
  if (activeScenario?.scenario_id) {
    return activeScenario.scenario_id;
  }
  return workspace.runtime_scenario_comparison.lead_scenario_id;
}

function buildTimelineStops(workspace: WorkspaceData): TimelineStop[] {
  const { scenario } = resolveActiveScenario(workspace);
  const tripDuration = workspace.trip_record.trip.trip_frame.duration_days;
  const routeSequence = scenario?.scenario_summary.route_sequence ?? [];

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
      startDay,
      endDay,
    };
  });
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

function buildScenarioReviewMetrics(
  workspace: WorkspaceData,
  scenario: WorkspaceData["runtime_scenario_comparison"]["scenarios"][number]
): ScenarioReviewMetric[] {
  return [
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
    {
      label: "Policy posture",
      value: formatPolicyPosture(workspace),
    },
  ];
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
      label: "approval-ready",
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
      label: "failed",
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
    return {
      state: "completed-with-follow-up",
      label: "completed with follow-up",
      title: "Policy review finished with follow-up",
      summary:
        summary.follow_up_summary ??
        "The live policy run completed and the workspace now needs remediation or exception handling.",
    };
  }

  if (submissionStatus === "deferred" || evaluationTransportStatus === "deferred") {
    return {
      state: "deferred",
      label: "deferred",
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
      label: "running",
      title: awaitingEvaluation ? "Awaiting policy evaluation result" : "Policy review is running",
      summary:
        summary.follow_up_summary ??
        summary.submission_summary ??
        "The workspace is waiting for the latest remote policy execution result.",
    };
  }

  return {
    state: "pending",
    label: "pending",
    title: "Proposal submission is pending",
    summary: "Build and submit the approval packet to start live policy execution for this workspace.",
  };
}

function hasRenderableFollowUp(
  followUp: NonNullable<WorkspaceData["proposal_state"]>["follow_up"]
): followUp is NonNullable<NonNullable<WorkspaceData["proposal_state"]>["follow_up"]> {
  return Boolean(followUp?.status && followUp?.title && followUp?.summary);
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

export function WorkspacePage() {
  const { workspace, trips } = useLoaderData() as LoaderData;

  return (
    <AsyncRouteContent
      resolve={Promise.all([workspace, trips ?? Promise.resolve([] as TripRecord[])])}
      loading={{
        label: "Workspace",
        title: "Loading persisted trip state",
        message: "Hydrating trip, session, and saved-scenario records for the timeline surface.",
      }}
      error={{
        label: "Workspace",
        title: "Workspace request failed",
        message: "The shared API client could not load the workspace payload.",
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
  const [selectedMapScenarioId, setSelectedMapScenarioId] = useState(() =>
    resolveMapScenarioId(workspace)
  );
  const [selectedScenarioComparisonId, setSelectedScenarioComparisonId] = useState<string | null>(
    () => workspace.runtime_scenario_comparison.lead_scenario_id
  );
  const [selectedTripComparisonId, setSelectedTripComparisonId] = useState<string | null>(
    () => trips.find((trip) => trip.trip_id !== workspace.trip_record.trip.trip_id)?.trip_id ?? null
  );
  const [plannerSession, setPlannerSession] = useState<PlannerSessionResponse | null>(null);
  const [plannerConversationDraft, setPlannerConversationDraft] = useState("");
  const [plannerConversationError, setPlannerConversationError] = useState<string | null>(null);
  const [plannerConversationBusyLabel, setPlannerConversationBusyLabel] = useState<string | null>(
    null
  );
  const [plannerError, setPlannerError] = useState<string | null>(null);
  const [plannerBusyLabel, setPlannerBusyLabel] = useState<string | null>(null);
  const [budgetError, setBudgetError] = useState<string | null>(null);
  const [budgetBusyLabel, setBudgetBusyLabel] = useState<string | null>(null);
  const [proposalError, setProposalError] = useState<string | null>(null);
  const [proposalBusyLabel, setProposalBusyLabel] = useState<string | null>(null);
  const plannerSessionLoadVersion = useRef(0);
  const isCompactLayout = useCompactWorkspaceLayout();
  useEffect(() => {
    setCurrentWorkspace(workspace);
    setSelectedMapScenarioId(resolveMapScenarioId(workspace));
    setSelectedScenarioComparisonId(
      workspace.runtime_scenario_comparison.lead_scenario_id
    );
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

  const timelineStops = buildTimelineStops(currentWorkspace);
  const { trip } = currentWorkspace.trip_record;
  const activeScenario = resolveActiveScenario(currentWorkspace);
  const activeRuntimeScenario =
    currentWorkspace.runtime_scenario_comparison.scenarios.find(
      (scenario) => scenario.scenario_id === (selectedMapScenarioId ?? activeScenario.scenario?.scenario_id)
    ) ??
    currentWorkspace.runtime_scenario_comparison.scenarios[0] ??
    null;
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
        <p className="status-label">Workspace timeline</p>
        <h2>{trip.title}</h2>
        <p>{trip.summary}</p>
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
            ? "Compact review stack keeps map, timeline, and tradeoff calls visible on smaller screens."
            : "Review-ready workspace keeps route context, daily pacing, and tradeoffs visible at once."}
        </p>
      </div>

      <div className="workspace-grid">
        <section className="status-card planner-panel-card">
          <p className="status-label">Planner panel</p>
          <h2>Trip-scoped planner surface</h2>
          <p className="muted-copy">
            {currentWorkspace.planner_panel_state.planner_behavior.runtime_summary ??
              "The existing planner side panel now mounts inside the workspace route and reads trip-scoped API data."}
          </p>
          <div className="planner-runtime-row" aria-label="Planner runtime state">
            <span
              className={`planner-runtime-pill planner-runtime-pill--${
                currentWorkspace.planner_panel_state.planner_behavior.runtime_status ?? "fallback"
              }`}
            >
              {currentWorkspace.planner_panel_state.planner_behavior.runtime_label ?? "Deterministic fallback planner"}
            </span>
            <span className="planner-runtime-mode">
              {currentWorkspace.planner_panel_state.planner_behavior.runtime_mode === "model"
                ? "Model-backed"
                : "Fallback"}
            </span>
          </div>
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
                <p className="scenario-kicker">Conversation runtime</p>
                <h3>Message the trip planner</h3>
                <p>
                  Turns are persisted through the trip-scoped planner API and refresh the same
                  panel state, memory, and activity trail used by the workspace.
                </p>
              </div>
              <span className="planner-conversation-pill">
                {plannerSession?.messages.length ?? 0} message
                {(plannerSession?.messages.length ?? 0) === 1 ? "" : "s"}
              </span>
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
                    No conversation turns have been persisted yet. Send a message to start the
                    runtime-backed planner thread for this trip.
                  </p>
                </article>
              ) : (
                plannerSession.messages.map((message) => (
                  <article
                    key={message.message_id}
                    className={`planner-message planner-message-${message.role}`}
                  >
                    <p className="scenario-kicker">
                      {message.role === "user" ? "Traveler" : "Planner"}
                    </p>
                    <p>{message.content}</p>
                    {message.tool_calls.length > 0 ? (
                      <ul className="planner-tool-call-list">
                        {message.tool_calls.map((toolCall) => (
                          <li key={`${message.message_id}-${toolCall.tool_name}`}>
                            {toolCall.tool_name}: {toolCall.summary}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </article>
                ))
              )}
            </div>
            {plannerSession?.available_tools.length ? (
              <div className="planner-tool-strip" aria-label="Planner tools available">
                {plannerSession.available_tools.slice(0, 4).map((tool) => (
                  <span key={tool.tool_name}>{tool.tool_name.replace(/_/g, " ")}</span>
                ))}
              </div>
            ) : null}
            <form className="planner-conversation-form" onSubmit={handlePlannerTurnSubmit}>
              <label>
                Message
                <textarea
                  value={plannerConversationDraft}
                  onChange={(event) => setPlannerConversationDraft(event.target.value)}
                  placeholder="Ask the planner what to compare, revise, or inspect next."
                  rows={3}
                />
              </label>
              <button type="submit" disabled={Boolean(plannerConversationBusyLabel)}>
                Send planner turn
              </button>
            </form>
          </section>
        </section>

        <WorkspaceBudgetPanel
          budgetState={currentWorkspace.budget_state}
          tripMode={trip.mode}
          busyLabel={budgetBusyLabel}
          errorMessage={budgetError}
          onSaveBudget={handleBudgetSave}
          onRecordSpend={handleSpendRecord}
        />

        <TripMap
          comparison={currentWorkspace.runtime_scenario_comparison}
          scenarioComparisonSummary={currentWorkspace.scenario_comparison?.summary}
          scenarioFocusAreas={currentWorkspace.scenario_comparison?.focus_areas ?? []}
          activeScenarioId={selectedMapScenarioId}
          onSelectScenario={setSelectedMapScenarioId}
          bundles={currentWorkspace.inventory_summary.bundles}
          feasibilitySummary={currentWorkspace.feasibility_summary}
          tripPrimaryRegions={trip.trip_frame.primary_regions}
          policyPosture={scenarioPolicyPosture}
          compactLayout={isCompactLayout}
        />

        <ScenarioComparison
          comparison={currentWorkspace.runtime_scenario_comparison}
          savedScenarios={currentWorkspace.saved_scenarios}
          selectedScenarioId={selectedScenarioComparisonId}
          onSelectScenario={setSelectedScenarioComparisonId}
        />

        <TripComparison
          currentTrip={currentWorkspace.trip_record.trip}
          trips={trips}
          selectedTripId={selectedTripComparisonId}
          onSelectTrip={setSelectedTripComparisonId}
        />

        <section className="status-card">
          <p className="status-label">Approval packet</p>
          <h2>{proposalLifecycle?.title ?? "Proposal lifecycle in progress"}</h2>
          {currentWorkspace.proposal_state == null ? (
            <p className="muted-copy">
              Proposal submission and evaluation records have not been persisted for this workspace yet.
            </p>
          ) : (
            <>
              {proposalBusyLabel ? <p className="muted-copy">{proposalBusyLabel}</p> : null}
              {proposalError ? <p className="planner-inline-error">{proposalError}</p> : null}
              <dl className="workspace-meta">
                <div>
                  <dt>Workspace state</dt>
                  <dd>{proposalLifecycle?.label ?? "pending"}</dd>
                </div>
                <div>
                  <dt>Submission</dt>
                  <dd>{currentWorkspace.proposal_state.summary.submission_status ?? "unknown"}</dd>
                </div>
                <div>
                  <dt>Transport</dt>
                  <dd>
                    {currentWorkspace.proposal_state.summary.evaluation_transport_status ??
                      currentWorkspace.proposal_state.evaluation_status ??
                      "pending"}
                  </dd>
                </div>
                <div>
                  <dt>Evaluation</dt>
                  <dd>{currentWorkspace.proposal_state.summary.evaluation_result_status ?? "pending"}</dd>
                </div>
                <div>
                  <dt>Comparables</dt>
                  <dd>{currentWorkspace.proposal_state.summary.comparable_count ?? 0}</dd>
                </div>
                <div>
                  <dt>Proposal version</dt>
                  <dd>{currentWorkspace.proposal_state.proposal_version}</dd>
                </div>
                <div>
                  <dt>Next step</dt>
                  <dd>
                    {formatFollowUpStatus(
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

        <section className="status-card">
          <p className="status-label">Inventory bundles</p>
          <h2>{workspace.inventory_summary.runtime_state.title}</h2>
          <p>{workspace.inventory_summary.runtime_state.summary}</p>
          <p className="muted-copy">{workspace.inventory_summary.notes[0]}</p>
          {workspace.inventory_summary.bundle_count === 0 ? (
            <p className="muted-copy">
              {workspace.inventory_summary.runtime_state.status === "partial"
                ? "Runtime bundle assembly is waiting on the rest of the trip frame."
                : "Bundle assembly has not started yet for this trip."}
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
          <p className="status-label">Timeline</p>
          {timelineStops.length === 0 || activeScenario.scenario === null ? (
            <>
              <h2>Timeline data is not ready</h2>
              <p>
                The workspace needs a scenario route sequence before it can render day-by-day pacing.
              </p>
              <p className="muted-copy">
                Trip context is ready now, so the next planning pass can attach saved scenarios and timeline stops.
              </p>
            </>
          ) : (
            <>
              <h2>{isCompactLayout ? "Compact day-by-day review" : "Trip rhythm and day sequencing"}</h2>
              <p>{activeScenario.scenario.scenario_summary.headline}</p>
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
                    {activeRuntimeScenario?.route_summary ??
                      activeScenario.scenario.scenario_summary.route_sequence.join(" -> ")}
                  </p>
                </article>
                <article className="timeline-summary-card">
                  <p className="scenario-kicker">Pacing</p>
                  <h3>
                    {activeRuntimeScenario == null
                      ? "Planner score pending"
                      : `${formatScenarioScore(activeRuntimeScenario.metrics.score)} planner score`}
                  </h3>
                  <p>{scenarioPolicyPosture} packet posture for the current workspace.</p>
                </article>
              </div>
              <ol className="timeline-list" aria-label="Trip timeline sequence">
                {timelineStops.map((stop) => (
                  <li key={stop.key} className="timeline-stop">
                    <div className="timeline-dayband">
                      <span>Day {stop.startDay}</span>
                      <span>Day {stop.endDay}</span>
                    </div>
                    <div>
                      <h3>{stop.label}</h3>
                      <p>
                        Days {stop.startDay}-{stop.endDay} keep this stop visible in the selected
                        scenario review path.
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </>
          )}
        </section>

        <section className="status-card">
          <p className="status-label">Scenario review board</p>
          <h2>{isCompactLayout ? "Compact scenario tradeoffs" : "Review-ready scenario tradeoffs"}</h2>
          <p>
            Cost, route burden, feasibility, and policy posture stay scannable here without
            forcing the traveler into raw scenario notes.
          </p>
          {currentWorkspace.runtime_scenario_comparison.scenarios.length > 0 ? (
            <div className="scenario-review-grid" aria-label="Scenario review board">
              {currentWorkspace.runtime_scenario_comparison.scenarios.map((scenario) => {
                const reviewMetrics = buildScenarioReviewMetrics(currentWorkspace, scenario);
                const isSelected = scenario.scenario_id === selectedScenarioComparisonId;

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
                          <dd>{metric.value}</dd>
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
                ? "Runtime comparison is waiting on richer trip inputs before scenario review can start."
                : "No runtime scenarios are available yet, so there is nothing to review in the scenario board."}
            </p>
          )}
        </section>

        <section className="status-card">
          <p className="status-label">Scenario context</p>
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
                No saved scenarios exist yet. The mounted planner panel carries the bootstrap context until planner
                history is persisted.
              </p>
            ) : null}
          </div>
        </section>
      </div>

      <div className="workspace-grid">
        <section className="status-card">
          <p className="status-label">Session state</p>
          <h2>Current planning posture</h2>
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
              <p className="muted-copy">No blocking decisions are currently waiting on the traveler.</p>
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
          <p className="status-label">Comparison</p>
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
            <p className="muted-copy">The workspace will surface durable scenario tradeoff comparisons here.</p>
          )}
        </section>

        <section className="status-card">
          <p className="status-label">Proposal details</p>
          <h2>Comparables and readiness signals</h2>
          {currentWorkspace.proposal_state == null ? (
            <p className="muted-copy">Approval-packet details will render here once a proposal is submitted.</p>
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
              {(currentWorkspace.proposal_state.proposal.comparables ?? []).map((comparable) => (
                <article
                  key={`${comparable.category}-${comparable.label}`}
                  className="decision-card"
                >
                  <h3>{comparable.label}</h3>
                  <p>
                    {comparable.vendor} via {comparable.booking_channel} ·{" "}
                    {formatCurrency(
                      comparable.estimated_cost.typical_amount,
                      comparable.estimated_cost.currency
                    )}
                  </p>
                  <p className="muted-copy">{comparable.notes.join(" ")}</p>
                </article>
              ))}
              {(currentWorkspace.proposal_state.evaluation.evaluation_result?.approval_requirements ?? []).map(
                (requirement) => (
                  <article key={requirement.role} className="decision-card">
                    <h3>{requirement.role}</h3>
                    <p>{requirement.reason}</p>
                  </article>
                )
              )}
              {(currentWorkspace.proposal_state.evaluation.evaluation_result?.failure_reasons ?? []).map(
                (failure) => (
                  <article key={failure.code} className="decision-card">
                    <h3>{failure.code.replace(/_/g, " ")}</h3>
                    <p>{failure.message}</p>
                  </article>
                )
              )}
            </div>
          )}
        </section>

        <section className="status-card">
          <p className="status-label">Planner memory</p>
          <h2>
            {currentWorkspace.planner_memory.artifacts.length > 0
              ? "User-visible planner checkpoints"
              : "Planner memory has not been summarized yet"}
          </h2>
          {currentWorkspace.planner_memory.artifacts.length === 0 ? (
            <p className="muted-copy">
              The workspace will surface durable planner summaries here after the first persisted
              planner conversation turn.
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
          <p className="status-label">Activity trail</p>
          <h2>Persisted planner actions</h2>
          <div className="decision-stack">
            {currentWorkspace.activity_log.length === 0 ? (
              <p className="muted-copy">Planner actions will appear here after the first persisted decision or feedback event.</p>
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
