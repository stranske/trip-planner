import type { ReactNode } from "react";

type PlannerRouteFocus = {
  title: string;
  summary: string;
};

type PlannerPanelProps = {
  runtimeMode: "model" | "fallback";
  runtimeStatus: string;
  routeFocus: PlannerRouteFocus | null;
  timelineNotes: string[];
  planningModeControl: ReactNode;
  busyLabel: string | null;
  errorMessage: string | null;
  plannerSurface: ReactNode;
  conversationPanel: ReactNode;
};

const PLANNER_PANEL_CLASS = "status-card planner-panel-card";

export function PlannerPanel({
  runtimeMode,
  runtimeStatus,
  routeFocus,
  timelineNotes,
  planningModeControl,
  busyLabel,
  errorMessage,
  plannerSurface,
  conversationPanel,
}: PlannerPanelProps) {
  return (
    <section className={PLANNER_PANEL_CLASS}>
      <p className="status-label">Planner</p>
      <h2>Traveler planning workspace</h2>
      <p className="muted-copy">
        Use your planner to compare options, keep context, and decide the next best trip step.
      </p>
      <div className="planner-runtime-row" aria-label="Planner availability">
        <span className={`planner-runtime-pill planner-runtime-pill--${runtimeStatus}`}>
          {runtimeMode === "model" ? "AI-assisted planner" : "Guided planner"}
        </span>
        <span className="planner-runtime-mode">
          {runtimeMode === "model" ? "Live assistance" : "Planning guide"}
        </span>
      </div>
      {routeFocus ? (
        <article className="planner-route-focus" aria-label="Planner route focus">
          <p className="scenario-kicker">Route focus</p>
          <h3>{routeFocus.title}</h3>
          <p>{routeFocus.summary}</p>
          {timelineNotes.length > 0 ? (
            <ul>
              {timelineNotes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}
        </article>
      ) : null}
      {planningModeControl}
      {busyLabel ? <p className="muted-copy">{busyLabel}</p> : null}
      {errorMessage ? <p className="planner-inline-error">{errorMessage}</p> : null}
      {plannerSurface}
      {conversationPanel}
    </section>
  );
}
