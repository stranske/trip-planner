import type { PlanningMode } from "../../api/workspace";

type PlanningModeOption = {
  value: PlanningMode;
  label: string;
  summary: string;
  help: string;
};

const PLANNING_MODE_OPTIONS: PlanningModeOption[] = [
  {
    value: "delegated",
    label: "Delegated",
    summary: "The planner drafts the next pass for you.",
    help: "Use this when you want the planner to organize the options, make a recommendation, and bring back a short decision for review.",
  },
  {
    value: "collaborative",
    label: "Collaborative",
    summary: "You and the planner work step by step.",
    help: "Use this when you want quick questions, visible tradeoffs, and frequent chances to steer before the plan changes.",
  },
  {
    value: "revealed-preference",
    label: "Revealed preference",
    summary: "Compare choices so your preferences become clearer.",
    help: "Use this when you are not sure what you prefer yet and want the planner to show route, lodging, pace, or budget tradeoffs.",
  },
  {
    value: "in-trip",
    label: "In-trip",
    summary: "Adapt the plan while travel is underway.",
    help: "Use this when something changed during the trip and you need practical adjustments without rebuilding everything.",
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
  const activeOption =
    PLANNING_MODE_OPTIONS.find((option) => option.value === value) ??
    PLANNING_MODE_OPTIONS[0];

  return (
    <section className="planning-mode-selector" aria-labelledby="planning-mode-selector-title">
      <div className="planning-mode-selector-header">
        <p className="scenario-kicker">Planner style</p>
        <h3 id="planning-mode-selector-title">How should the planner work?</h3>
        <p className="muted-copy">
          Choose how much initiative the planner should take on the next planning pass.
        </p>
      </div>
      <div className="planning-mode-options" role="radiogroup" aria-label="Planning mode">
        {PLANNING_MODE_OPTIONS.map((option) => (
          <label
            key={option.value}
            className={`planning-mode-option${
              option.value === value ? " planning-mode-option-active" : ""
            }`}
            title={option.help}
          >
            <input
              type="radio"
              name="planning-mode"
              value={option.value}
              checked={option.value === value}
              disabled={busy}
              aria-describedby={`planning-mode-${option.value}-summary planning-mode-${option.value}-help`}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
            <small id={`planning-mode-${option.value}-summary`}>{option.summary}</small>
            <small id={`planning-mode-${option.value}-help`} className="planning-mode-detail">
              {option.help}
            </small>
          </label>
        ))}
      </div>
      <p className="planning-mode-active-summary">
        Current mode: {activeOption.help}
      </p>
      {busy ? <p className="muted-copy">Saving planning mode...</p> : null}
      {error ? <p className="planner-inline-error">{error}</p> : null}
    </section>
  );
}
