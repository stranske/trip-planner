import { startTransition, useEffect, useState } from "react";
import { useLoaderData } from "react-router-dom";

import type { TripRecord } from "../api/trips";
import {
  answerPlannerDecision,
  recordWorkspaceSpendEvent,
  saveWorkspaceBudget,
  type ActualSpendEventUpsertPayload,
  type BudgetPlanUpsertPayload,
  type BudgetWorkspaceState,
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
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
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
  const [plannerError, setPlannerError] = useState<string | null>(null);
  const [plannerBusyLabel, setPlannerBusyLabel] = useState<string | null>(null);
  const [budgetError, setBudgetError] = useState<string | null>(null);
  const [budgetBusyLabel, setBudgetBusyLabel] = useState<string | null>(null);
  useEffect(() => {
    setCurrentWorkspace(workspace);
    setSelectedMapScenarioId(resolveMapScenarioId(workspace));
    setSelectedScenarioComparisonId(
      workspace.runtime_scenario_comparison.lead_scenario_id
    );
    setSelectedTripComparisonId(
      trips.find((trip) => trip.trip_id !== workspace.trip_record.trip.trip_id)?.trip_id ?? null
    );
  }, [trips, workspace]);

  const timelineStops = buildTimelineStops(currentWorkspace);
  const { trip } = currentWorkspace.trip_record;
  const activeScenario = resolveActiveScenario(currentWorkspace);
  const proposalFollowUp = currentWorkspace.proposal_state?.follow_up ?? null;
  const renderableProposalFollowUp = hasRenderableFollowUp(proposalFollowUp)
    ? proposalFollowUp
    : null;

  async function handleDecisionAnswer(decisionId: string, choice: string) {
    setPlannerError(null);
    setPlannerBusyLabel("Saving planner decision...");
    try {
      const nextWorkspace = await answerPlannerDecision(trip.trip_id, decisionId, choice);
      startTransition(() => {
        setCurrentWorkspace(nextWorkspace);
      });
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
      startTransition(() => {
        setCurrentWorkspace(nextWorkspace);
      });
    } catch (error) {
      setPlannerError(error instanceof Error ? error.message : "Planner feedback update failed.");
    } finally {
      setPlannerBusyLabel(null);
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

  return (
    <section className="workspace-layout">
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
      </div>

      <div className="workspace-grid">
        <section className="status-card planner-panel-card">
          <p className="status-label">Planner panel</p>
          <h2>Trip-scoped planner surface</h2>
          <p className="muted-copy">
            The existing planner side panel now mounts inside the workspace route and reads trip-scoped API data.
          </p>
          {plannerBusyLabel ? <p className="muted-copy">{plannerBusyLabel}</p> : null}
          {plannerError ? <p className="planner-inline-error">{plannerError}</p> : null}
          <PlannerSidePanelSurface
            state={currentWorkspace.planner_panel_state}
            onDecisionAnswer={handleDecisionAnswer}
            onOptionFeedback={handleOptionFeedback}
          />
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
          activeScenarioId={selectedMapScenarioId}
          onSelectScenario={setSelectedMapScenarioId}
          bundles={currentWorkspace.inventory_summary.bundles}
          feasibilitySummary={currentWorkspace.feasibility_summary}
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
          <h2>
            {currentWorkspace.proposal_state?.summary.approval_ready
              ? "Approval packet is ready"
              : "Proposal lifecycle in progress"}
          </h2>
          {currentWorkspace.proposal_state == null ? (
            <p className="muted-copy">
              Proposal submission and evaluation records have not been persisted for this workspace yet.
            </p>
          ) : (
            <>
              <dl className="workspace-meta">
                <div>
                  <dt>Submission</dt>
                  <dd>{currentWorkspace.proposal_state.summary.submission_status ?? "unknown"}</dd>
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
              <p>{currentWorkspace.proposal_state.summary.submission_summary ?? "Submission stored for later review."}</p>
              {renderableProposalFollowUp ? (
                <article className="decision-card">
                  <h3>{renderableProposalFollowUp.title}</h3>
                  <p>{renderableProposalFollowUp.summary}</p>
                  {renderableProposalFollowUp.guidance &&
                  renderableProposalFollowUp.guidance.length > 0 ? (
                    <p className="muted-copy">{renderableProposalFollowUp.guidance[0]}</p>
                  ) : null}
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
          <h2>Assembled inventory layer</h2>
          <p className="muted-copy">{workspace.inventory_summary.notes[0]}</p>
          {workspace.inventory_summary.bundle_count === 0 ? (
            <p className="muted-copy">
              Bundle assembly has not started yet for this trip.
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
              <h2>{activeScenario.scenario.title}</h2>
              <p>{activeScenario.scenario.scenario_summary.headline}</p>
              <ol className="timeline-list">
                {timelineStops.map((stop) => (
                  <li key={stop.key} className="timeline-stop">
                    <div className="timeline-dayband">
                      <span>Day {stop.startDay}</span>
                      <span>Day {stop.endDay}</span>
                    </div>
                    <div>
                      <h3>{stop.label}</h3>
                      <p>
                        Derived from the scenario route sequence and the persisted trip frame.
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </>
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
              {proposalFollowUp ? (
                <article className="decision-card">
                  <h3>{proposalFollowUp.recommended_label ?? proposalFollowUp.title}</h3>
                  <p>{proposalFollowUp.summary}</p>
                  {proposalFollowUp.selected_alternative?.summary ? (
                    <p className="muted-copy">
                      Selected alternative: {proposalFollowUp.selected_alternative.summary}
                    </p>
                  ) : null}
                  {proposalFollowUp.requested_exception?.reason ? (
                    <p className="muted-copy">
                      Exception rationale: {proposalFollowUp.requested_exception.reason}
                    </p>
                  ) : null}
                </article>
              ) : null}
              {(proposalFollowUp?.alternatives ?? []).map((alternative) => (
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
