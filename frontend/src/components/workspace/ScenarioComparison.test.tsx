import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RuntimeScenarioComparison } from "../../api/workspace";
import { ScenarioComparison } from "./ScenarioComparison";

afterEach(() => {
  cleanup();
});

const emptyComparison: RuntimeScenarioComparison = {
  title: "Saved scenario comparison",
  summary: "Runtime scenario rows have not been assembled yet.",
  lead_scenario_id: null,
  comparison_axes: [],
  scenarios: [],
  source_refs: [],
};

const singleScenarioComparison: RuntimeScenarioComparison = {
  title: "Rail vs flight comparison",
  summary: "One scenario is ready for side-by-side review.",
  lead_scenario_id: "scenario:rail-first",
  comparison_axes: [
    { key: "travel_minutes", label: "Travel minutes", direction: "lower_better" },
  ],
  scenarios: [
    {
      scenario_id: "scenario:rail-first",
      title: "Rail-first route",
      rank: 1,
      status: "recommended",
      summary: "A low-friction rail sequence through the main cities.",
      comparison_note: "Lead scenario for the current comparison set.",
      option_count: 2,
      route_sequence: ["stockholm", "oslo"],
      route_summary: "stockholm -> oslo",
      recommended_for_selection: true,
      feasible: true,
      metrics: {
        score: 0.82,
        travel_minutes: 420,
        transfers: 3,
        estimated_total: { currency: "USD", typical_amount: 3600 },
      },
      delta: {
        score_delta: 0,
        travel_minutes_delta: 0,
        transfers_delta: 0,
        estimated_total_delta: 0,
      },
      highlights: ["Balanced movement with clear rail legs."],
    },
  ],
  source_refs: ["scenario-search:demo"],
};

describe("ScenarioComparison", () => {
  it("renders the empty state when no runtime scenarios are present", () => {
    render(
      <ScenarioComparison
        comparison={emptyComparison}
        savedScenarios={[]}
        selectedScenarioId={null}
        onSelectScenario={vi.fn()}
      />
    );

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "Saved-scenario comparison is not ready"
    );
  });

  it("renders the comparison title and a scenario metric for a single scenario", () => {
    render(
      <ScenarioComparison
        comparison={singleScenarioComparison}
        savedScenarios={[]}
        selectedScenarioId={null}
        onSelectScenario={vi.fn()}
      />
    );

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "Rail vs flight comparison"
    );
    expect(screen.getByText("Time").closest("div")).toHaveTextContent("420 min");
  });

  it("invokes onSelectScenario when a scenario chip is clicked", () => {
    const onSelectScenario = vi.fn();

    render(
      <ScenarioComparison
        comparison={singleScenarioComparison}
        savedScenarios={[]}
        selectedScenarioId={null}
        onSelectScenario={onSelectScenario}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Compare 1. Rail-first route" })
    );

    expect(onSelectScenario).toHaveBeenCalledWith("scenario:rail-first");
  });
});
