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
    summary: "Planner leads and returns a clear next step.",
    help: "Use this when you want your planner to organize options, make a recommendation, and return one next decision to confirm.",
  },
  {
    value: "collaborative",
    label: "Collaborative",
    summary: "Traveler and planner work together step by step.",
    help: "Use this when you want quick questions, visible tradeoffs, and frequent checkpoints before the trip plan changes.",
  },
  {
    value: "revealed-preference",
    label: "Revealed preference",
    summary: "Compare options to uncover what matters most.",
    help: "Use this when you are still deciding and want your planner to surface route, lodging, pace, or budget tradeoffs.",
  },
  {
    value: "in-trip",
    label: "In-trip",
    summary: "Adjust the trip while you are already traveling.",
    help: "Use this when plans changed mid-trip and you need practical adjustments without rebuilding everything.",
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
        <p className="scenario-kicker">Traveler control</p>
        <h3 id="planning-mode-selector-title">How should the planner work?</h3>
        <p className="muted-copy">
          Choose how much initiative your planner should take for the next trip step.
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
        Active guidance: {activeOption.help}
      </p>
      {busy ? <p className="muted-copy">Saving planning mode...</p> : null}
      {error ? <p className="planner-inline-error">{error}</p> : null}
    </section>
  );
}
