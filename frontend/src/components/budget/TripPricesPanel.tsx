import { useEffect, useState } from "react";

import type { TripPriceComponent, TripPricesState } from "../../api/workspace";
import { formatInstantDate } from "../../lib/dates";
import { formatMoney } from "../../lib/money";

export type TripPricesPanelProps = {
  prices: TripPricesState | null;
  busy: boolean;
  errorMessage: string | null;
  onSave: (
    component: string,
    amount: number | null,
    note: string,
    fareDetail?: FareDetail
  ) => void;
};

export type FareDetail = {
  lowestAmount: number | null;
  evidenceAttested: boolean;
  cabinClass: string | null;
  flightHours: number | null;
};

const CABIN_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "economy", label: "Economy" },
  { value: "premium_economy", label: "Premium economy" },
  { value: "business", label: "Business" },
  { value: "first", label: "First" },
];

/** The one component TPP's fare rules read. */
const FARE_COMPONENT = "transport";

function sourceLine(component: TripPriceComponent): string | null {
  if (component.price_source == null) {
    return null;
  }
  const captured = formatInstantDate(component.price_source.captured_at);
  return `Entered by ${component.price_source.attributed_to} on ${captured}`;
}

export function TripPricesPanel({ prices, busy, errorMessage, onSave }: TripPricesPanelProps) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [lowestFare, setLowestFare] = useState("");
  const [evidenceAttested, setEvidenceAttested] = useState(false);
  const [cabinClass, setCabinClass] = useState("");
  const [flightHours, setFlightHours] = useState("");

  // Re-seed the inputs whenever saved prices arrive, so the fields show what is stored
  // rather than whatever was last typed.
  useEffect(() => {
    if (prices == null) {
      return;
    }
    setDrafts(
      Object.fromEntries(
        prices.components.map((component) => [
          component.component,
          component.typical_amount == null ? "" : String(component.typical_amount),
        ])
      )
    );
    setNotes(
      Object.fromEntries(
        prices.components.map((component) => [component.component, component.note])
      )
    );
    const fare = prices.components.find((component) => component.component === FARE_COMPONENT);
    setLowestFare(fare?.lowest_amount == null ? "" : String(fare.lowest_amount));
    setEvidenceAttested(Boolean(fare?.evidence_attested));
    setCabinClass(fare?.cabin_class ?? "");
    setFlightHours(fare?.flight_hours == null ? "" : String(fare.flight_hours));
  }, [prices]);

  if (prices == null) {
    return (
      <section className="status-card">
        <p className="status-label">Trip cost</p>
        <p className="muted-copy">Loading the prices recorded for this trip…</p>
      </section>
    );
  }

  return (
    <section className="status-card" aria-label="Trip cost">
      <p className="status-label">Trip cost</p>
      <h2>What this trip costs</h2>
      <p className="field-hint">
        This planner does not have a pricing source connected yet, so it will not show you a
        figure it cannot stand behind. Enter the amounts you already have — from your
        corporate booking tool, an airline site, a quote — and they appear on the approval
        packet attributed to you.
      </p>

      {errorMessage != null ? (
        <p className="form-error" role="alert" data-testid="trip-prices-error">
          {errorMessage}
        </p>
      ) : null}

      <dl className="workspace-meta">
        <div>
          <dt>Total</dt>
          <dd data-testid="trip-prices-total">
            {formatMoney(prices.total)}
            {prices.total != null ? (
              <span className="muted-copy">
                {" "}
                — entered by {prices.total.price_source.attributed_to}
              </span>
            ) : null}
          </dd>
        </div>
        <div>
          <dt>Still unpriced</dt>
          {/* The blocking quantity and the drainable quantity in the same place: a panel
              that only reports what is missing reads as broken, not as awaiting input. */}
          <dd data-testid="trip-prices-unpriced-count">
            {prices.unpriced_component_count} of {prices.components.length} — enter a figure
            below to reduce this
          </dd>
        </div>
      </dl>

      <ul className="trip-price-list">
        {prices.components.map((component) => {
          const attribution = sourceLine(component);
          return (
            <li key={component.component} className="trip-price-row">
              <label htmlFor={`trip-price-${component.component}`}>{component.label}</label>
              <input
                id={`trip-price-${component.component}`}
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                placeholder="Not priced"
                value={drafts[component.component] ?? ""}
                disabled={busy}
                onChange={(event) =>
                  setDrafts((current) => ({
                    ...current,
                    [component.component]: event.target.value,
                  }))
                }
              />
              <input
                type="text"
                aria-label={`Where the ${component.label} figure came from`}
                placeholder="Where did this come from?"
                value={notes[component.component] ?? ""}
                disabled={busy}
                onChange={(event) =>
                  setNotes((current) => ({
                    ...current,
                    [component.component]: event.target.value,
                  }))
                }
              />
              <button
                type="button"
                disabled={busy}
                aria-label={`${component.typical_amount == null ? "Save" : "Update"} ${component.label}`}
                onClick={() => {
                  const raw = (drafts[component.component] ?? "").trim();
                  const lowestRaw = lowestFare.trim();
                  onSave(
                    component.component,
                    raw === "" ? null : Number(raw),
                    notes[component.component] ?? "",
                    component.component === FARE_COMPONENT
                      ? {
                          lowestAmount: lowestRaw === "" ? null : Number(lowestRaw),
                          evidenceAttested,
                          cabinClass: cabinClass === "" ? null : cabinClass,
                          flightHours: flightHours.trim() === "" ? null : Number(flightHours),
                        }
                      : undefined
                  );
                }}
              >
                {component.typical_amount == null ? "Save" : "Update"}
              </button>
              {component.typical_amount != null ? (
                <button
                  type="button"
                  className="link-button"
                  disabled={busy}
                  aria-label={`Remove ${component.label}`}
                  onClick={() => onSave(component.component, null, "")}
                >
                  Remove
                </button>
              ) : null}
              {component.component === FARE_COMPONENT ? (
                <div className="trip-price-fare-detail">
                  <label htmlFor="trip-price-lowest-fare">
                    Lowest fare you found for the same journey
                  </label>
                  <input
                    id="trip-price-lowest-fare"
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    placeholder="Optional"
                    value={lowestFare}
                    disabled={busy}
                    onChange={(event) => setLowestFare(event.target.value)}
                  />
                  <label htmlFor="trip-price-cabin">Cabin booked</label>
                  <select
                    id="trip-price-cabin"
                    value={cabinClass}
                    disabled={busy}
                    onChange={(event) => setCabinClass(event.target.value)}
                  >
                    <option value="">Not given</option>
                    {CABIN_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <label htmlFor="trip-price-flight-hours">Longest flight, in hours</label>
                  <input
                    id="trip-price-flight-hours"
                    type="number"
                    min="0"
                    max="30"
                    step="0.25"
                    inputMode="decimal"
                    placeholder="From your itinerary"
                    value={flightHours}
                    disabled={busy}
                    onChange={(event) => setFlightHours(event.target.value)}
                  />
                  <label className="trip-price-attest">
                    <input
                      type="checkbox"
                      checked={evidenceAttested}
                      disabled={busy}
                      onChange={(event) => setEvidenceAttested(event.target.checked)}
                    />
                    I have a screenshot or other fare evidence to give my approver
                  </label>
                  <p className="field-hint">
                    Travel policy compares your fare with the lowest available, checks the
                    cabin against the flight time, and asks for evidence of the fare. Take all
                    four from your airline quote; without them approval is blocked whatever the
                    fare.
                  </p>
                </div>
              ) : null}
              <p className="field-hint" data-testid={`trip-price-source-${component.component}`}>
                {attribution ??
                  (component.component === "other"
                    ? "No source has priced this yet. Enter 0 if there are none, so the trip counts as fully priced."
                    : "No source has priced this yet.")}
              </p>
            </li>
          );
        })}
      </ul>
      <p className="field-hint">
        Clearing a figure removes it entirely. A stale number on an approval request is no
        better than an invented one.
      </p>
    </section>
  );
}
