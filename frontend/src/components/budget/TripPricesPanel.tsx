import { useEffect, useState } from "react";

import type { TripPriceComponent, TripPricesState } from "../../api/workspace";
import { formatMoney } from "../../lib/money";

export type TripPricesPanelProps = {
  prices: TripPricesState | null;
  busy: boolean;
  errorMessage: string | null;
  onSave: (component: string, amount: number | null, note: string) => void;
};

function sourceLine(component: TripPriceComponent): string | null {
  if (component.price_source == null) {
    return null;
  }
  const captured = component.price_source.captured_at.slice(0, 10);
  return `Entered by ${component.price_source.attributed_to} on ${captured}`;
}

export function TripPricesPanel({ prices, busy, errorMessage, onSave }: TripPricesPanelProps) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});

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

      <ul className="focus-area-list trip-price-list">
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
                onClick={() => {
                  const raw = (drafts[component.component] ?? "").trim();
                  onSave(
                    component.component,
                    raw === "" ? null : Number(raw),
                    notes[component.component] ?? ""
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
                  onClick={() => onSave(component.component, null, "")}
                >
                  Remove
                </button>
              ) : null}
              <p className="field-hint" data-testid={`trip-price-source-${component.component}`}>
                {attribution ?? "No source has priced this yet."}
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
