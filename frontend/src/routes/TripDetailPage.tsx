import { Link, useLoaderData } from "react-router-dom";

import type { PlanningHistoryEntry, TripRecord, TripScenarioHistoryData } from "../api/trips";
import { formatCalendarDate, formatInstantDate } from "../lib/dates";
import { AsyncRouteContent } from "../lib/routes/AsyncRouteContent";

type LoaderData = {
  tripDetail: Promise<{
    trip: TripRecord;
    scenarioHistory: TripScenarioHistoryData;
  }>;
};

export function TripDetailPage() {
  const { tripDetail } = useLoaderData() as LoaderData;

  return (
    <AsyncRouteContent
      resolve={tripDetail}
      loading={{
        label: "Trip detail",
        title: "Loading saved trip",
        message:
          "Reading the trip and its recent activity.",
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

const PARTY_LABELS: Record<string, string> = {
  solo: "Just me",
  pair: "Two of us",
  family: "Family",
  friends: "Friends",
  team: "Work team",
};

/**
 * A readable summary of one trip, with the way back into it (issue 1844). It used to be a
 * dump of stored records: session ids, "Persisted scenario shelf", "Active workflow
 * memory", raw ISO timestamps, and no link to the plan.
 */
function TripDetailContent({
  trip,
  scenarioHistory,
}: {
  trip: TripRecord;
  scenarioHistory: TripScenarioHistoryData;
}) {
  const frame = trip.trip_frame;
  const journey = [frame.origin, ...frame.primary_regions].filter(Boolean).join(" → ");
  const party = frame.traveler_party;
  const recent = scenarioHistory.planning_history.slice(0, 5);

  return (
    <section className="workspace-layout">
      <article className="status-card workspace-hero">
        <p className="status-label">{trip.mode === "business" ? "Business trip" : "Personal trip"}</p>
        <h2>{trip.title}</h2>
        <p>{trip.summary || "No purpose written yet."}</p>
        <p className="workspace-hero-actions">
          <Link to={`/workspace/${trip.trip_id}`}>Open plan</Link>
          {" · "}
          <Link to={`/trips/${trip.trip_id}/edit`}>Edit trip setup</Link>
        </p>
        <dl className="workspace-meta">
          <div>
            <dt>Journey</dt>
            <dd data-testid="trip-detail-journey">{journey || "No destination yet"}</dd>
          </div>
          <div>
            <dt>Dates</dt>
            <dd>
              {frame.start_date && frame.end_date
                ? `${formatCalendarDate(frame.start_date)} to ${formatCalendarDate(frame.end_date)}`
                : frame.start_date
                  ? `Starts ${formatCalendarDate(frame.start_date)}`
                  : frame.end_date
                    ? `Ends ${formatCalendarDate(frame.end_date)}`
                    : "Not set"}
            </dd>
          </div>
          <div>
            <dt>Length</dt>
            <dd>{frame.duration_days ? `${frame.duration_days} days` : "Not set"}</dd>
          </div>
          <div>
            <dt>Travellers</dt>
            <dd>
              {party.traveler_count} ({PARTY_LABELS[party.kind] ?? party.kind})
            </dd>
          </div>
          {party.notes ? (
            <div>
              <dt>Notes</dt>
              <dd>{party.notes}</dd>
            </div>
          ) : null}
        </dl>
      </article>

      <section className="status-card">
        <p className="status-label">Recent activity</p>
        <h2>What has happened on this trip</h2>
        {recent.length === 0 ? (
          <p className="muted-copy">Nothing has been planned on this trip yet.</p>
        ) : (
          <ul className="trip-detail-activity">
            {recent.map((entry: PlanningHistoryEntry) => (
              <li key={entry.activity_event_id}>
                {entry.summary}{" "}
                <span className="muted-copy">({formatInstantDate(entry.occurred_at)})</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
