import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BudgetWorkspaceState } from "../../api/workspace";
import { WorkspaceBudgetPanel } from "./WorkspaceBudgetPanel";

afterEach(() => {
  cleanup();
});

const budgetState: BudgetWorkspaceState = {
  budget_plan: {
    budget_plan_id: "budget:kyoto",
    trip_id: "trip:kyoto",
    owner_profile_id: "profile:traveler",
    title: "Leisure trip budget",
    mode: "leisure",
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    scenario_budgets: [
      {
        scenario_budget_id: "scenario-budget:kyoto",
        saved_scenario_id: "saved-scenario:kyoto",
        title: "Kyoto baseline",
        summary: "Baseline budget",
        tags: [],
        notes: [],
        allocations: [
          {
            category_key: "lodging",
            label: "Lodging",
            planned_amount: 1200,
            currency: "USD",
            flexibility: "flexible",
            notes: [],
          },
        ],
      },
    ],
    current_scenario_budget_id: "scenario-budget:kyoto",
    currency: "USD",
    schema_version: "1",
    tags: [],
    notes: [],
  },
  versions: [
    {
      version_id: "budget-version:1",
      budget_plan_id: "budget:kyoto",
      recorded_at: "2026-08-01T00:00:00Z",
      summary: "Initial budget",
    },
  ],
  spend_events: [],
  summary: {
    currency: "USD",
    has_budget_plan: true,
    current_scenario_budget_id: "scenario-budget:kyoto",
    current_scenario_title: "Kyoto baseline",
    planned_total: 1200,
    actual_total: 0,
    remaining_total: 1200,
    spend_event_count: 0,
    version_count: 1,
    suggested_categories: ["lodging"],
    category_summaries: [
      {
        category_key: "lodging",
        label: "Lodging",
        currency: "USD",
        planned_amount: 1200,
        actual_amount: 0,
        remaining_amount: 1200,
        flexibility: "flexible",
      },
    ],
  },
};

describe("WorkspaceBudgetPanel", () => {
  it("unsaved budget edits survive a refresh", async () => {
    const user = userEvent.setup();
    const onSaveBudget = vi.fn().mockResolvedValue(undefined);
    const onRecordSpend = vi.fn().mockResolvedValue(undefined);
    const props = {
      tripMode: "leisure",
      busyLabel: null,
      errorMessage: null,
      onSaveBudget,
      onRecordSpend,
    };
    const view = render(<WorkspaceBudgetPanel budgetState={budgetState} {...props} />);

    const title = screen.getByRole("textbox", { name: "Budget title" });
    await user.clear(title);
    await user.type(title, "Unsaved Kyoto edits");

    view.rerender(
      <WorkspaceBudgetPanel
        budgetState={{ ...budgetState, budget_plan: { ...budgetState.budget_plan! } }}
        {...props}
      />
    );

    expect(title).toHaveValue("Unsaved Kyoto edits");
  });

  it("never prints a negative zero, and says when no budget is set (issue 1843)", () => {
    const props = {
      tripMode: "business",
      busyLabel: null,
      errorMessage: null,
      onSaveBudget: vi.fn(),
      onRecordSpend: vi.fn(),
    };
    const unset: BudgetWorkspaceState = {
      ...budgetState,
      budget_plan: null,
      summary: {
        ...budgetState.summary,
        has_budget_plan: false,
        planned_total: 0,
        remaining_total: -0,
        category_summaries: [],
      },
    };
    const view = render(<WorkspaceBudgetPanel budgetState={unset} {...props} />);
    expect(view.container.textContent ?? "").not.toMatch(/-\$0/);
    expect(screen.getByTestId("budget-remaining-total")).toHaveTextContent("No budget set");
    view.unmount();

    const drained: BudgetWorkspaceState = {
      ...budgetState,
      summary: { ...budgetState.summary, remaining_total: -0.001 },
    };
    const second = render(<WorkspaceBudgetPanel budgetState={drained} {...props} />);
    expect(screen.getByTestId("budget-remaining-total")).toHaveTextContent("$0.00");
    expect(second.container.textContent ?? "").not.toMatch(/-\$0/);
    expect(second.container.textContent ?? "").not.toMatch(/should feed later planner/);
  });
});
