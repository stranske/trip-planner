import { useLoaderData } from "react-router-dom";

import { type SavedScenarioRecord, type WorkspaceData } from "../api/workspace";
import { PlannerSidePanelSurface } from "../components/planner/PlannerSidePanelSurface";
import { AsyncRouteContent } from "../lib/routes/AsyncRouteContent";

type LoaderData = {
  workspace: Promise<WorkspaceData>;
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
    return startDate ?? endDate ?? "Dates not set yet";
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
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(value));
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

export function WorkspacePage() {
  const { workspace } = useLoaderData() as LoaderData;

  return (
    <AsyncRouteContent
      resolve={workspace}
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
      {(resolvedWorkspace) => <WorkspacePageContent workspace={resolvedWorkspace} />}
    </AsyncRouteContent>
  );
}

function WorkspacePageContent({ workspace }: { workspace: WorkspaceData }) {
  const timelineStops = buildTimelineStops(workspace);
  const { trip } = workspace.trip_record;
  const activeScenario = resolveActiveScenario(workspace);

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
              {trip.trip_frame.duration_days ? `${trip.trip_frame.duration_days} days` : "Duration not set yet"}
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
          <PlannerSidePanelSurface state={workspace.planner_panel_state} />
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
          <h2>{workspace.scenario_search.title}</h2>
          <div className="scenario-stack">
            {workspace.saved_scenarios.map((savedScenario) => {
              const activeVersion = savedScenario.versions.find(
                (version) => version.version_id === savedScenario.current_version_id
              );

              return (
                <ScenarioSummaryCard
                  key={savedScenario.saved_scenario_id}
                  savedScenario={savedScenario}
                  activeVersion={activeVersion}
                  isActive={savedScenario.saved_scenario_id === workspace.session.current_saved_scenario_id}
                />
              );
            })}
            {workspace.saved_scenarios.length === 0 ? (
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
              <dd>{workspace.session.interaction_state.interaction_style}</dd>
            </div>
            <div>
              <dt>Initiative</dt>
              <dd>{workspace.session.interaction_state.initiative_level}</dd>
            </div>
            <div>
              <dt>Checkpointing</dt>
              <dd>{workspace.session.interaction_state.checkpoint_frequency}</dd>
            </div>
          </dl>
          <div className="decision-stack">
            {workspace.session.pending_decisions.length === 0 ? (
              <p className="muted-copy">No blocking decisions are currently waiting on the traveler.</p>
            ) : (
              workspace.session.pending_decisions.map((decision) => (
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
          <h2>{workspace.scenario_comparison?.summary ?? "No comparison saved yet"}</h2>
          {workspace.scenario_comparison ? (
            <>
              <p>Outcome: {workspace.scenario_comparison.outcome}</p>
              <ul className="focus-area-list">
                {workspace.scenario_comparison.focus_areas.map((focusArea) => (
                  <li key={focusArea}>{focusArea.replace(/_/g, " ")}</li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted-copy">The workspace will surface durable scenario tradeoff comparisons here.</p>
          )}
        </section>
      </div>
    </section>
  );
}
