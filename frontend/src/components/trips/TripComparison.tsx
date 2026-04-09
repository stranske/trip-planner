import type { TripRecord } from "../../api/trips";

type TripComparisonTripFrame = Pick<TripRecord["trip_frame"], "duration_days"> &
  Partial<Pick<TripRecord["trip_frame"], "primary_regions" | "traveler_party">>;

type TripComparisonRecord = Pick<
  TripRecord,
  "trip_id" | "title" | "summary" | "mode" | "status"
> & {
  trip_frame: TripComparisonTripFrame;
};

function summarizeRegions(regions: string[]): string {
  if (regions.length === 0) {
    return "No primary regions saved";
  }
  return regions.join(", ");
}

function buildTripDelta(currentTrip: TripComparisonRecord, comparedTrip: TripRecord): string {
  const currentDuration = currentTrip.trip_frame.duration_days;
  const comparedDuration = comparedTrip.trip_frame.duration_days;
  if (currentDuration == null || comparedDuration == null) {
    return "Duration delta unavailable";
  }
  const delta = comparedDuration - currentDuration;
  return `${delta >= 0 ? "+" : ""}${delta} day delta versus current trip`;
}

export function TripComparison({
  currentTrip,
  trips,
  selectedTripId,
  onSelectTrip,
}: {
  currentTrip: TripComparisonRecord;
  trips: TripRecord[];
  selectedTripId: string | null;
  onSelectTrip: (tripId: string) => void;
}) {
  const comparisonCandidates = trips.filter((trip) => trip.trip_id !== currentTrip.trip_id);
  const selectedTrip =
    comparisonCandidates.find((trip) => trip.trip_id === selectedTripId) ??
    comparisonCandidates[0] ??
    null;

  if (comparisonCandidates.length === 0 || selectedTrip == null) {
    return (
      <section className="status-card">
        <p className="status-label">Trip comparison</p>
        <h2>Trip-to-trip comparison will appear as more persisted trips land</h2>
        <p className="muted-copy">
          The current workspace can already compare saved scenarios. Cross-trip comparison needs at least one more saved trip from the persisted trips API.
        </p>
      </section>
    );
  }

  return (
    <section className="status-card">
      <p className="status-label">Trip comparison</p>
      <h2>Compare this workspace with other saved trips</h2>
      <p>
        Cross-trip selection uses persisted trip records so travelers can evaluate whether the current workspace still fits the broader trip slate.
      </p>
      <div className="map-scenario-toggle" aria-label="Trip comparison choices">
        {comparisonCandidates.map((trip) => (
          <button
            key={trip.trip_id}
            type="button"
            className={`map-toggle-chip${trip.trip_id === selectedTrip.trip_id ? " map-toggle-chip-active" : ""}`}
            aria-pressed={trip.trip_id === selectedTrip.trip_id}
            onClick={() => onSelectTrip(trip.trip_id)}
          >
            Compare with {trip.title}
          </button>
        ))}
      </div>
      <div className="scenario-stack">
        {[currentTrip, selectedTrip].map((trip) => (
          <article key={trip.trip_id} className="scenario-card">
            <p className="scenario-kicker">{trip.trip_id === currentTrip.trip_id ? "current workspace" : "saved trip"}</p>
            <h3>{trip.title}</h3>
            <p>{trip.summary || "No trip summary captured yet."}</p>
            <dl className="workspace-meta">
              <div>
                <dt>Mode</dt>
                <dd>{trip.mode}</dd>
              </div>
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
                <dd>{summarizeRegions(trip.trip_frame.primary_regions ?? [])}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
      <div className="decision-stack" aria-label="Trip comparison summary">
        <article className="decision-card">
          <h3>Trip frame delta</h3>
          <p>{buildTripDelta(currentTrip, selectedTrip)}</p>
          <p className="muted-copy">
            {selectedTrip.title} is stored as a {selectedTrip.mode} trip with{" "}
            {selectedTrip.trip_frame.traveler_party?.traveler_count ?? "unknown"} traveler(s).
          </p>
        </article>
        <article className="decision-card">
          <h3>Region overlap</h3>
          <p>
            Current trip: {summarizeRegions(currentTrip.trip_frame.primary_regions ?? [])}
          </p>
          <p>
            Compared trip: {summarizeRegions(selectedTrip.trip_frame.primary_regions)}
          </p>
        </article>
      </div>
    </section>
  );
}
