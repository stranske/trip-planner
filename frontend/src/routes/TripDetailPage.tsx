import { useLoaderData } from "react-router-dom";

import type { TripRecord } from "../api/trips";
import { AsyncRouteContent } from "../lib/routes/AsyncRouteContent";

type LoaderData = {
  trip: Promise<TripRecord>;
};

function formatValue(value: string | null): string {
  return value || "TBD";
}

export function TripDetailPage() {
  const { trip } = useLoaderData() as LoaderData;

  return (
    <AsyncRouteContent
      resolve={trip}
      loading={{
        label: "Trip detail",
        title: "Loading saved trip",
        message: "Restoring the persisted trip payload and ownership-aware metadata.",
      }}
      error={{
        label: "Trip detail",
        title: "Trip detail unavailable",
        message: "The app could not load this trip record.",
      }}
    >
      {(resolvedTrip) => <TripDetailContent trip={resolvedTrip} />}
    </AsyncRouteContent>
  );
}

function TripDetailContent({ trip }: { trip: TripRecord }) {
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
      </div>
    </section>
  );
}
