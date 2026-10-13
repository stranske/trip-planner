import { useState, type FormEvent } from "react";

export type PortalTravelerAnswers = Record<string, string>;

export function PortalTravelerAnswersForm({ disabled, prepared = false, onSubmit }: {
  disabled: boolean;
  prepared?: boolean;
  onSubmit: (answers?: PortalTravelerAnswers) => void;
}) {
  const [answers, setAnswers] = useState<PortalTravelerAnswers>({});
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(Object.fromEntries(Object.entries(answers).filter(([, value]) => value !== "")));
  }
  if (prepared) return <button type="button" className="primary-button" disabled={disabled}
    onClick={() => onSubmit()}>Reopen approver portal</button>;
  const fields = [
    ["destination_zip", "Destination ZIP", "text", true],
    ["booking_date", "Booking date", "date", true],
    ["selected_fare", "Selected flight fare (USD)", "number", false],
    ["lowest_fare", "Lowest available fare (USD)", "number", false],
    ["flight_duration_hours", "Flight duration (hours)", "number", false],
  ] as const;
  return <form onSubmit={submit} aria-label="Complete approver portal answers">
    <p>Enter missing traveler details. Saved trip and price facts cannot be replaced here.</p>
    <fieldset disabled={disabled}>
      <legend>Approver portal details</legend>
      {fields.map(([name, label, type, required]) => <label key={name}>
        {label}
        <input name={name} type={type} required={required} min={type === "number" ? "0" : undefined}
          step={type === "number" ? "any" : undefined} value={answers[name] ?? ""}
          onChange={(event) => setAnswers((current) => ({ ...current, [name]: event.target.value }))} />
      </label>)}
      <label>Cabin class<select value={answers.cabin_class ?? ""}
        onChange={(event) => setAnswers((current) => ({ ...current, cabin_class: event.target.value }))}>
        <option value="">Use saved cabin</option><option value="economy">Economy</option>
        <option value="premium_economy">Premium economy</option><option value="business">Business</option>
        <option value="first">First</option>
      </select></label>
      <label>Fare evidence attached<select value={answers.fare_evidence_attached ?? ""}
        onChange={(event) => setAnswers((current) => ({ ...current, fare_evidence_attached: event.target.value }))}>
        <option value="">Use saved attestation</option><option value="true">Yes, I have fare evidence</option>
        <option value="false">No</option>
      </select></label>
      <button type="submit" className="primary-button">Send to my approver</button>
    </fieldset>
  </form>;
}
