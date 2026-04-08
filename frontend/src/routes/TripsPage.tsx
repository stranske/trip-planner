import { Link, useLoaderData } from "react-router-dom";

import type { TripRecord } from "../api/trips";
import { AsyncRouteContent } from "../lib/routes/AsyncRouteContent";

type LoaderData = {
  trips: Promise<TripRecord[]>;
};

function summarizeRegions(regions: string[]): string {
  if (regions.length === 0) {
    return "No primary regions captured yet";
  }
  return regions.join(", ");
}

export function TripsPage() {
  const { trips } = useLoaderData() as LoaderData;

  return (
    <AsyncRouteContent
      resolve={trips}
      loading={{
        label: "Trips",
        title: "Loading saved trips",
        message: "Restoring the persisted planning containers for this signed-in traveler.",
      }}
      error={{
        label: "Trips",
        title: "Trip list unavailable",
        message: "The app could not load the saved trip list.",
      }}
    >
      {(resolvedTrips) => <TripsPageContent trips={resolvedTrips} />}
    </AsyncRouteContent>
  );
}

function TripsPageContent({ trips }: { trips: TripRecord[] }) {
  return (
    <section className="workspace-layout">
      <article className="status-card">
        <p className="status-label">Saved trips</p>
        <h2>Persisted planning containers</h2>
        <p className="lede">
          Each trip record is now the durable root object for later scenario, budget, and policy work.
        </p>
        <Link className="cta-link" to="/trips/new">
          Create a trip
        </Link>
      </article>

      {trips.length === 0 ? (
        <article className="status-card">
          <p className="status-label">No trips yet</p>
          <h2>Start the first saved itinerary container</h2>
          <p className="muted-copy">Create a trip to persist title, timing, traveler party, and ownership.</p>
        </article>
      ) : (
        <section className="trip-grid">
          {trips.map((trip) => (
            <article key={trip.trip_id} className="status-card trip-card">
              <p className="status-label">{trip.mode}</p>
              <h2>{trip.title}</h2>
              <p>{trip.summary || "No trip summary captured yet."}</p>
              <dl className="workspace-meta">
                <div>
                  <dt>Status</dt>
                  <dd>{trip.status}</dd>
                </div>
                <div>
                  <dt>Duration</dt>
                  <dd>{trip.trip_frame.duration_days ?? "TBD"} days</dd>
                </div>
                <div>
                  <dt>Regions</dt>
                  <dd>{summarizeRegions(trip.trip_frame.primary_regions)}</dd>
                </div>
              </dl>
              <Link className="cta-link" to={`/trips/${trip.trip_id}`}>
                Open trip detail
              </Link>
            </article>
          ))}
        </section>
      )}
    </section>
  );
}
