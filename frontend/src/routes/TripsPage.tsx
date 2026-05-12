import { startTransition, useEffect, useState } from "react";
import { Link, useLoaderData } from "react-router-dom";

import { deleteTrip, type TripRecord } from "../api/trips";
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
  const [visibleTrips, setVisibleTrips] = useState(trips);
  const [confirmingTripId, setConfirmingTripId] = useState<string | null>(null);
  const [deletingTripId, setDeletingTripId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    setVisibleTrips(trips);
  }, [trips]);

  async function handleDeleteTrip(trip: TripRecord) {
    setDeleteError(null);
    setDeletingTripId(trip.trip_id);
    try {
      await deleteTrip(trip.trip_id);
      startTransition(() => {
        setVisibleTrips((current) =>
          current.filter((candidate) => candidate.trip_id !== trip.trip_id)
        );
        setConfirmingTripId(null);
      });
    } catch (error) {
      setDeleteError(
        error instanceof Error ? error.message : `Could not delete ${trip.title}.`
      );
    } finally {
      setDeletingTripId(null);
    }
  }

  return (
    <section className="workspace-layout">
      <article className="status-card">
        <p className="status-label">Saved trips</p>
        <h2>Your trips</h2>
        <p className="lede">
          Open a trip to keep planning, or remove a trip you no longer need.
        </p>
        <Link className="cta-link" to="/trips/new">
          Create a trip
        </Link>
      </article>

      {deleteError ? (
        <p className="planner-inline-error" role="alert">
          {deleteError}
        </p>
      ) : null}

      {visibleTrips.length === 0 ? (
        <article className="status-card">
          <p className="status-label">No trips yet</p>
          <h2>Start your first trip</h2>
          <p className="muted-copy">Create a trip to save dates, places, travelers, and planning notes.</p>
        </article>
      ) : (
        <section className="trip-grid">
          {visibleTrips.map((trip) => (
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
              <div className="trip-card-actions">
                <Link className="cta-link" to={`/workspace/${trip.trip_id}`}>
                  Open planner
                </Link>
                <Link className="secondary-link" to={`/trips/${trip.trip_id}`}>
                  Details
                </Link>
                <button
                  type="button"
                  className="secondary-button danger-button"
                  disabled={deletingTripId === trip.trip_id}
                  onClick={() =>
                    setConfirmingTripId((current) =>
                      current === trip.trip_id ? null : trip.trip_id
                    )
                  }
                >
                  Delete
                </button>
              </div>
              {confirmingTripId === trip.trip_id ? (
                <div className="trip-delete-confirmation" role="group" aria-label={`Confirm delete ${trip.title}`}>
                  <p>
                    Delete this trip and its saved planning work? This cannot be undone.
                  </p>
                  <button
                    type="button"
                    className="danger-button"
                    disabled={deletingTripId === trip.trip_id}
                    onClick={() => handleDeleteTrip(trip)}
                  >
                    {deletingTripId === trip.trip_id ? "Deleting..." : "Yes, delete trip"}
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={deletingTripId === trip.trip_id}
                    onClick={() => setConfirmingTripId(null)}
                  >
                    Cancel
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </section>
      )}
    </section>
  );
}
