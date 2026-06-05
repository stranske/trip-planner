import { FormEvent, startTransition, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createTrip } from "../api/trips";
import { getErrorMessage } from "../lib/api/errors";

export function NewTripPage() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    const formData = new FormData(event.currentTarget);

    try {
      const trip = await createTrip({
        title: String(formData.get("title") ?? ""),
        summary: String(formData.get("summary") ?? ""),
        mode: String(formData.get("mode") ?? "leisure"),
        trip_frame: {
          start_date: String(formData.get("startDate") ?? "") || null,
          end_date: String(formData.get("endDate") ?? "") || null,
          duration_days: Number(formData.get("durationDays") ?? 0) || null,
          primary_regions: String(formData.get("primaryRegions") ?? "")
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
          traveler_party: {
            kind: String(formData.get("travelerKind") ?? "solo"),
            traveler_count: Number(formData.get("travelerCount") ?? 1) || 1,
            notes: String(formData.get("travelerNotes") ?? ""),
          },
        },
      });
      startTransition(() => {
        navigate(`/workspace/${trip.trip_id}`);
      });
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "Trip creation failed."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-layout">
      <article className="status-card auth-card">
        <p className="status-label">New trip</p>
        <h2>Create a trip</h2>
        <p className="lede">
          Add the basics now. You can refine routes, notes, budget, and decisions in the planner.
        </p>
        <form className="auth-form" onSubmit={handleSubmit}>
          <fieldset>
            <legend>Trip basics</legend>
            <label>
              Title
              <input name="title" type="text" required />
            </label>
            <label>
              Summary
              <input name="summary" type="text" />
            </label>
            <label>
              Mode
              <select name="mode" defaultValue="leisure">
                <option value="leisure">Leisure</option>
                <option value="business">Business</option>
              </select>
            </label>
            <label>
              Primary regions
              <input name="primaryRegions" type="text" placeholder="Kyoto, Osaka" />
            </label>
          </fieldset>
          <fieldset>
            <legend>When</legend>
            <label>
              Start date
              <input name="startDate" type="date" />
            </label>
            <label>
              End date
              <input name="endDate" type="date" />
            </label>
            <label>
              Duration days
              <input name="durationDays" type="number" min={1} defaultValue={7} />
            </label>
          </fieldset>
          <fieldset>
            <legend>Travelers</legend>
            <label>
              Traveler party
              <select name="travelerKind" defaultValue="solo">
                <option value="solo">Solo</option>
                <option value="pair">Pair</option>
                <option value="family">Family</option>
                <option value="friends">Friends</option>
                <option value="team">Team</option>
              </select>
            </label>
            <label>
              Traveler count
              <input name="travelerCount" type="number" min={1} defaultValue={1} />
            </label>
            <label>
              Traveler notes
              <input name="travelerNotes" type="text" />
            </label>
          </fieldset>
          {errorMessage ? (
            <p className="auth-error" role="alert">
              {errorMessage}
            </p>
          ) : null}
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating trip..." : "Create trip"}
          </button>
        </form>
      </article>
    </section>
  );
}
