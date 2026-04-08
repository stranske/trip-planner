import { useLoaderData } from "react-router-dom";

import type {
  PlanningHistoryEntry,
  PlanningSessionRecord,
  SavedScenarioRecord,
  TripRecord,
  TripScenarioHistoryData,
} from "../api/trips";
import { AsyncRouteContent } from "../lib/routes/AsyncRouteContent";

type LoaderData = {
  tripDetail: Promise<{
    trip: TripRecord;
    scenarioHistory: TripScenarioHistoryData;
  }>;
};

function formatValue(value: string | null): string {
  return value || "TBD";
}

export function TripDetailPage() {
  const { tripDetail } = useLoaderData() as LoaderData;

  return (
    <AsyncRouteContent
      resolve={tripDetail}
      loading={{
        label: "Trip detail",
        title: "Loading saved trip",
        message:
          "Restoring the persisted trip, planning-session context, and trip-level audit trail.",
      }}
      error={{
        label: "Trip detail",
        title: "Trip detail unavailable",
        message: "The app could not load this trip record.",
      }}
    >
      {({ trip, scenarioHistory }) => (
        <TripDetailContent trip={trip} scenarioHistory={scenarioHistory} />
      )}
    </AsyncRouteContent>
  );
}

function formatScenarioLabel(label: string): string {
  return label.split("_").join(" ");
}

function renderCurrentVersion(savedScenario: SavedScenarioRecord) {
  const currentVersion =
    savedScenario.versions.find(
      (version) => version.version_id === savedScenario.current_version_id
    ) ?? savedScenario.versions[0];

  if (currentVersion) {
    return currentVersion;
  }

  return {
    version_id: savedScenario.current_version_id,
    label: "unavailable",
    title: "Unavailable",
    summary: "This saved scenario is missing version details.",
  };
}

function summarizeHistory(entry: PlanningHistoryEntry): string {
  return entry.event_kind.split("_").join(" ");
}

function summarizeSession(session: PlanningSessionRecord): string {
  return session.status.split("_").join(" ");
}

function TripDetailContent({
  trip,
  scenarioHistory,
}: {
  trip: TripRecord;
  scenarioHistory: TripScenarioHistoryData;
}) {
  return (
    <section className="workspace-layout">
      <article className="status-card workspace-hero">
        <p className="status-label">Trip detail</p>
        <h2>{trip.title}</h2>
        <p>{trip.summary || "No summary saved yet."}</p>
        <dl className="workspace-meta">
          <div>
            <dt>Trip ID</dt>
            <dd>{trip.trip_id}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{trip.status}</dd>
          </div>
          <div>
            <dt>Mode</dt>
            <dd>{trip.mode}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>{trip.trip_frame.duration_days ?? "TBD"} days</dd>
          </div>
        </dl>
      </article>

      <div className="workspace-grid">
        <section className="status-card">
          <p className="status-label">Frame</p>
          <h2>Travel timing</h2>
          <dl className="workspace-meta">
            <div>
              <dt>Start</dt>
              <dd>{formatValue(trip.trip_frame.start_date)}</dd>
            </div>
            <div>
              <dt>End</dt>
              <dd>{formatValue(trip.trip_frame.end_date)}</dd>
            </div>
            <div>
              <dt>Regions</dt>
              <dd>{trip.trip_frame.primary_regions.join(", ") || "TBD"}</dd>
            </div>
          </dl>
        </section>

        <section className="status-card">
          <p className="status-label">Traveler party</p>
          <h2>{trip.trip_frame.traveler_party.kind}</h2>
          <dl className="workspace-meta">
            <div>
              <dt>Travelers</dt>
              <dd>{trip.trip_frame.traveler_party.traveler_count}</dd>
            </div>
            <div>
              <dt>Notes</dt>
              <dd>{trip.trip_frame.traveler_party.notes || "No extra notes yet."}</dd>
            </div>
          </dl>
        </section>

        <section className="status-card">
          <p className="status-label">Saved scenarios</p>
          <h2>Persisted scenario shelf</h2>
          {scenarioHistory.saved_scenarios.length === 0 ? (
            <p className="muted-copy">
              No saved scenarios have been persisted for this trip yet.
            </p>
          ) : (
            <div className="scenario-stack">
              {scenarioHistory.saved_scenarios.map((savedScenario) => {
                const currentVersion = renderCurrentVersion(savedScenario);
                return (
                  <article
                    key={savedScenario.saved_scenario_id}
                    className="scenario-card scenario-card-active"
                  >
                    <p className="scenario-kicker">
                      {formatScenarioLabel(currentVersion.label)}
                    </p>
                    <h3>{currentVersion.title}</h3>
                    <p>{currentVersion.summary || "No scenario summary captured yet."}</p>
                    <dl className="workspace-meta">
                      <div>
                        <dt>Versions</dt>
                        <dd>{savedScenario.versions.length}</dd>
                      </div>
                      <div>
                        <dt>Scenario ID</dt>
                        <dd>{savedScenario.saved_scenario_id}</dd>
                      </div>
                    </dl>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="status-card">
          <p className="status-label">Planning session</p>
          <h2>Active workflow memory</h2>
          {scenarioHistory.planning_sessions.length === 0 ? (
            <p className="muted-copy">
              No planning session has been persisted for this trip yet.
            </p>
          ) : (
            <div className="decision-stack">
              {scenarioHistory.planning_sessions.map((session) => (
                <article key={session.session_state_id} className="decision-card">
                  <p className="scenario-kicker">{summarizeSession(session)}</p>
                  <h3>{session.session_state_id}</h3>
                  <p>
                    Initiative {session.interaction_state.initiative_level} with{" "}
                    {session.pending_decisions.length} pending decisions and{" "}
                    {session.recent_option_presentations.length} recent option surfaces.
                  </p>
                  <dl className="workspace-meta">
                    <div>
                      <dt>Updated</dt>
                      <dd>{session.updated_at}</dd>
                    </div>
                    <div>
                      <dt>Activity log</dt>
                      <dd>{session.activity_log_id || "Not linked yet"}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="status-card">
          <p className="status-label">Planning history</p>
          <h2>Trip-level activity timeline</h2>
          {scenarioHistory.planning_history.length === 0 ? (
            <p className="muted-copy">
              No planning-history entries have been recorded for this trip yet.
            </p>
          ) : (
            <div className="decision-stack">
              {scenarioHistory.planning_history.map((entry) => (
                <article
                  key={entry.activity_event_id}
                  className="decision-card"
                >
                  <p className="scenario-kicker">{summarizeHistory(entry)}</p>
                  <h3>{entry.summary}</h3>
                  <p>
                    {entry.actor} at {entry.occurred_at}
                  </p>
                  <p>Session {entry.session_state_id}</p>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
