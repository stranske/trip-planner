import { FormEvent, startTransition, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createTrip, updateTrip, type TripRecord } from "../api/trips";
import { getErrorMessage } from "../lib/api/errors";

type TripMode = "business" | "leisure";

const MODE_CHOICES: Array<{ value: TripMode; label: string; description: string }> = [
  {
    value: "business",
    label: "Business trip",
    description:
      "Needs employer approval. The planner checks your plan against travel policy and builds an approval packet you can print.",
  },
  {
    value: "leisure",
    label: "Personal trip",
    description: "No approval step. The planner focuses on routes, pacing, and budget for your own use.",
  },
];

const PARTY_CHOICES: Array<{ value: string; label: string }> = [
  { value: "solo", label: "Just me" },
  { value: "pair", label: "Two of us" },
  { value: "family", label: "Family" },
  { value: "friends", label: "Friends" },
  { value: "team", label: "Work team" },
];

/** Whole days between two ISO dates, inclusive of the start day. */
export function travelDaysInclusive(startDate: string, endDate: string): number | null {
  if (!startDate || !endDate) {
    return null;
  }
  const start = Date.parse(`${startDate}T00:00:00Z`);
  const end = Date.parse(`${endDate}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) {
    return null;
  }
  return Math.round((end - start) / 86_400_000) + 1;
}

/** Fields the planner needs before it can assemble anything worth reviewing. */
export function missingTripContext(values: {
  mode: TripMode | "";
  origin?: string;
  purpose: string;
  destinations: string;
  startDate: string;
  endDate: string;
}): string[] {
  const missing: string[] = [];
  if (!values.mode) {
    missing.push("trip type");
  }
  if (!(values.origin ?? "").trim()) {
    missing.push("a starting point");
  }
  if (!values.destinations.split(";").some((destination) => destination.trim())) {
    missing.push("at least one destination");
  }
  if (travelDaysInclusive(values.startDate, values.endDate) == null) {
    missing.push("travel dates");
  }
  if (values.mode === "business" && !values.purpose.trim()) {
    missing.push("a business purpose");
  }
  return missing;
}

/** Shown on the workspace after an edit removed a saved policy verdict. */
export const VERDICT_CLEARED_NOTICE =
  "Trip setup saved. The earlier travel policy result was removed because the trip changed; submit it again for a new result.";

/**
 * Trip setup. With `existingTrip` it edits that trip (issue 1841): setup always promised
 * "You can change any of this later", and until now nothing could.
 */
export function NewTripPage({ existingTrip = null }: { existingTrip?: TripRecord | null } = {}) {
  const navigate = useNavigate();
  const isEditing = existingTrip != null;
  const existingFrame = existingTrip?.trip_frame;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [mode, setMode] = useState<TripMode | "">(
    existingTrip?.mode === "business" || existingTrip?.mode === "leisure" ? existingTrip.mode : ""
  );
  const [title, setTitle] = useState(existingTrip?.title ?? "");
  const [purpose, setPurpose] = useState(existingTrip?.summary ?? "");
  const [origin, setOrigin] = useState(existingFrame?.origin ?? "");
  const [destinations, setDestinations] = useState((existingFrame?.primary_regions ?? []).join("; "));
  const [startDate, setStartDate] = useState(existingFrame?.start_date ?? "");
  const [endDate, setEndDate] = useState(existingFrame?.end_date ?? "");
  const [durationOverride, setDurationOverride] = useState<string>(
    existingFrame?.duration_days != null &&
      existingFrame.duration_days !==
        travelDaysInclusive(existingFrame.start_date ?? "", existingFrame.end_date ?? "")
      ? String(existingFrame.duration_days)
      : ""
  );
  const [travelerKind, setTravelerKind] = useState(existingFrame?.traveler_party.kind ?? "solo");
  const [travelerCount, setTravelerCount] = useState(
    String(existingFrame?.traveler_party.traveler_count ?? 1)
  );
  const [travelerNotes, setTravelerNotes] = useState(existingFrame?.traveler_party.notes ?? "");

  const derivedDuration = useMemo(() => travelDaysInclusive(startDate, endDate), [startDate, endDate]);
  const durationValue = durationOverride !== "" ? durationOverride : derivedDuration != null ? String(derivedDuration) : "";
  const datesInvalid = Boolean(startDate && endDate && derivedDuration == null);
  const destinationList = destinations
    .split(";")
    .map((value) => value.trim())
    .filter(Boolean);
  const tooManyDestinations = destinationList.length > 8;

  const missing = missingTripContext({ mode, origin, purpose, destinations, startDate, endDate });
  const isBusiness = mode === "business";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) {
      setErrorMessage("Enter a trip name before creating the trip.");
      return;
    }
    if (datesInvalid || tooManyDestinations) {
      return;
    }
    setIsSubmitting(true);
    setErrorMessage(null);

    const tripFrame = {
      origin: origin.trim() || null,
      start_date: startDate || null,
      end_date: endDate || null,
      duration_days: durationValue ? Number(durationValue) : null,
      primary_regions: destinationList,
      traveler_party: {
        kind: travelerKind,
        traveler_count: Number(travelerCount) || 1,
        notes: travelerNotes.trim(),
      },
    };
    try {
      if (existingTrip) {
        const { verdictCleared } = await updateTrip(existingTrip.trip_id, {
          title: title.trim(),
          summary: purpose.trim(),
          trip_frame: tripFrame,
        });
        startTransition(() => {
          navigate(`/workspace/${existingTrip.trip_id}`, {
            state: { setupNotice: verdictCleared ? VERDICT_CLEARED_NOTICE : "Trip setup saved." },
          });
        });
        return;
      }
      const trip = await createTrip({
        title: title.trim(),
        summary: purpose.trim(),
        mode: mode || "leisure",
        trip_frame: tripFrame,
      });
      startTransition(() => {
        navigate(`/workspace/${trip.trip_id}`);
      });
    } catch (error) {
      setErrorMessage(
        getErrorMessage(error, isEditing ? "Saving the trip setup failed." : "Trip creation failed.")
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-layout">
      <article className="status-card auth-card setup-card">
        <p className="status-label">{isEditing ? "Trip setup" : "New trip"}</p>
        <h2>{isEditing ? "Edit trip setup" : "Set up your trip"}</h2>
        <p className="lede">
          {isEditing
            ? "Change anything below. The route is measured again from the new setup; your entered prices and notes stay. If the trip was already checked against travel policy, changing its purpose, origin, dates, destinations or travellers removes that result."
            : "Tell the planner the essentials and it will measure the route and travel time from your origin. You enter the prices you hold. You can change any of this later."}
        </p>

        <form className="auth-form setup-form" onSubmit={handleSubmit}>
          <fieldset className="setup-group">
            <legend>What kind of trip is this?</legend>
            <p className="field-hint">
              {isEditing
                ? "The trip type cannot be changed after the trip is created."
                : "This decides whether the trip goes through travel policy and approval."}
            </p>
            <div className="choice-grid" role="radiogroup" aria-label="Trip type">
              {MODE_CHOICES.map((choice) => (
                <label
                  key={choice.value}
                  className={`choice-card${mode === choice.value ? " choice-card-selected" : ""}`}
                >
                  <input
                    type="radio"
                    name="mode"
                    value={choice.value}
                    checked={mode === choice.value}
                    onChange={() => setMode(choice.value)}
                    disabled={isEditing}
                    required
                  />
                  <span className="choice-title">{choice.label}</span>
                  <span className="choice-description">{choice.description}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="setup-group">
            <legend>The basics</legend>

            <label>
              Trip name
              <input
                name="title"
                type="text"
                required
                maxLength={160}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Client visit — Chicago"
              />
            </label>
            <p className="field-hint">How you will recognise this trip in your list.</p>

            <label>
              {isBusiness ? "Business purpose" : "What is this trip for?"}
              <input
                name="summary"
                type="text"
                maxLength={600}
                value={purpose}
                onChange={(event) => setPurpose(event.target.value)}
                placeholder={
                  isBusiness ? "Quarterly review with the Northwind account team" : "Long weekend away"
                }
              />
            </label>
            <p className="field-hint">
              {isBusiness
                ? "Approvers read this first. One sentence on why the travel is necessary."
                : "Optional. A short note about the purpose of the trip."}
            </p>

            <label>
              Travelling from
              <input
                name="origin"
                type="text"
                maxLength={120}
                value={origin}
                onChange={(event) => setOrigin(event.target.value)}
                placeholder="Seattle"
              />
            </label>
            <p className="field-hint">
              Where the journey starts. The planner measures the route from here, so distance and
              travel time depend on it.
            </p>

            <label>
              Destinations
              <input
                name="primaryRegions"
                type="text"
                value={destinations}
                onChange={(event) => setDestinations(event.target.value)}
                placeholder="Chicago, IL"
                aria-invalid={tooManyDestinations}
                aria-describedby={tooManyDestinations ? "destinations-hint destinations-error" : "destinations-hint"}
              />
            </label>
            <p className="field-hint" id="destinations-hint">
              Where you are going. Separate multiple stops with semicolons — up to 8.
              {destinationList.length > 0 ? ` Currently ${destinationList.length}.` : ""}
            </p>
            {tooManyDestinations ? (
              <p className="field-error" id="destinations-error" role="alert">
                That is more than 8 destinations. Remove a few, or plan them as separate trips.
              </p>
            ) : null}
          </fieldset>

          <fieldset className="setup-group">
            <legend>When are you travelling?</legend>
            <p className="field-hint">
              For business trips the dates decide which policy rates apply.
            </p>

            <label>
              First day of travel
              <input
                name="startDate"
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                aria-invalid={datesInvalid}
                aria-describedby={datesInvalid ? "dates-error" : undefined}
              />
            </label>

            <label>
              Last day of travel
              <input
                name="endDate"
                type="date"
                value={endDate}
                min={startDate || undefined}
                onChange={(event) => setEndDate(event.target.value)}
                aria-invalid={datesInvalid}
                aria-describedby={datesInvalid ? "dates-error" : undefined}
              />
            </label>

            {datesInvalid ? (
              <p className="field-error" id="dates-error" role="alert">
                The last day is before the first day. Check the dates.
              </p>
            ) : null}

            <label>
              Trip length (days)
              <input
                name="durationDays"
                type="number"
                min={1}
                max={365}
                value={durationValue}
                onChange={(event) => setDurationOverride(event.target.value)}
              />
            </label>
            <p className="field-hint">
              {derivedDuration != null
                ? `Worked out from your dates (${derivedDuration} days). Change it if the travel days differ.`
                : "Fill in both dates and this is worked out for you."}
            </p>
          </fieldset>

          <fieldset className="setup-group">
            <legend>Who is travelling?</legend>

            <label>
              Travelling as
              <select
                name="travelerKind"
                value={travelerKind}
                onChange={(event) => setTravelerKind(event.target.value)}
              >
                {PARTY_CHOICES.map((choice) => (
                  <option key={choice.value} value={choice.value}>
                    {choice.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Number of travellers
              <input
                name="travelerCount"
                type="number"
                min={1}
                max={50}
                value={travelerCount}
                onChange={(event) => setTravelerCount(event.target.value)}
              />
            </label>
            <p className="field-hint">Tells the approver how many people are travelling.</p>

            <label>
              Anything the planner should know
              <input
                name="travelerNotes"
                type="text"
                maxLength={240}
                value={travelerNotes}
                onChange={(event) => setTravelerNotes(event.target.value)}
                placeholder="Arriving a day early; prefer non-stop flights"
              />
            </label>
            <p className="field-hint">Optional. Accessibility needs, preferences, fixed commitments.</p>
          </fieldset>

          <aside className="setup-next" aria-label="What happens next">
            <p className="status-label">What happens next</p>
            {missing.length > 0 ? (
              <p className="setup-next-blocked">
                Still needed before the planner can assemble options: {missing.join(", ")}.
              </p>
            ) : (
              <p>
                The planner will measure the route options from your origin.
                {isBusiness
                  ? " You will then enter the prices you hold, check the trip against travel policy, and print an approval packet."
                  : " You can then enter the prices you hold and keep notes as you decide."}
              </p>
            )}
          </aside>

          {errorMessage ? (
            <p className="auth-error" role="alert">
              {errorMessage}
            </p>
          ) : null}

          <button type="submit" disabled={isSubmitting || datesInvalid || tooManyDestinations}>
            {isEditing
              ? isSubmitting
                ? "Saving..."
                : "Save changes"
              : isSubmitting
                ? "Creating trip..."
                : "Create trip"}
          </button>
        </form>
      </article>
    </section>
  );
}
