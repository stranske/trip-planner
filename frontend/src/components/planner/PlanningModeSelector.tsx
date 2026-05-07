import type { PlanningMode } from "../../api/workspace";

type PlanningModeOption = {
  value: PlanningMode;
  label: string;
  summary: string;
};

const PLANNING_MODE_OPTIONS: PlanningModeOption[] = [
  {
    value: "delegated",
    label: "Delegated",
    summary: "Planner leads the next pass.",
  },
  {
    value: "collaborative",
    label: "Collaborative",
    summary: "Planner and traveler iterate together.",
  },
  {
    value: "revealed-preference",
    label: "Revealed preference",
    summary: "Options expose tradeoffs for choice.",
  },
  {
    value: "in-trip",
    label: "In-trip",
    summary: "Adjust live constraints and pacing.",
  },
];

export function PlanningModeSelector({
  value,
  busy,
  error,
  onChange,
}: {
  value: PlanningMode;
  busy?: boolean;
  error?: string | null;
  onChange: (mode: PlanningMode) => void;
}) {
  return (
    <section className="planning-mode-selector" aria-labelledby="planning-mode-selector-title">
      <div className="planning-mode-selector-header">
        <p className="scenario-kicker">Planner control</p>
        <h3 id="planning-mode-selector-title">Planning mode</h3>
      </div>
      <div className="planning-mode-options" role="radiogroup" aria-label="Planning mode">
        {PLANNING_MODE_OPTIONS.map((option) => (
          <label
            key={option.value}
            className={`planning-mode-option${
              option.value === value ? " planning-mode-option-active" : ""
            }`}
          >
            <input
              type="radio"
              name="planning-mode"
              value={option.value}
              checked={option.value === value}
              disabled={busy}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
            <small>{option.summary}</small>
          </label>
        ))}
      </div>
      {busy ? <p className="muted-copy">Saving planning mode...</p> : null}
      {error ? <p className="planner-inline-error">{error}</p> : null}
    </section>
  );
}
