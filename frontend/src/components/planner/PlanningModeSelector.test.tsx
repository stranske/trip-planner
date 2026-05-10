import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PlanningModeSelector } from "./PlanningModeSelector";

describe("PlanningModeSelector", () => {
  it("renders the active mode and emits changes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <PlanningModeSelector
        value="collaborative"
        busy={false}
        error={null}
        onChange={onChange}
      />
    );

    expect(screen.getByRole("radio", { name: /Collaborative/ })).toBeChecked();
    expect(
      screen.getAllByText(/quick questions, visible tradeoffs, and frequent checkpoints/).length
    ).toBeGreaterThan(0);
    expect(screen.getByLabelText(/Delegated/).closest("label")).toHaveAttribute(
      "title",
      expect.stringContaining("organize the options")
    );

    await user.click(screen.getByRole("radio", { name: /In-trip/ }));

    expect(onChange).toHaveBeenCalledWith("in-trip");
  });
});
