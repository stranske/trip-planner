import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PortalHandoffStatus } from "./PortalHandoffStatus";

describe("PortalHandoffStatus", () => {
  it.each(["approved", "rejected", "changes_requested"] as const)(
    "displays the recorded %s decision and its observation time",
    (decision) => {
      render(
        <PortalHandoffStatus
          handoff={{
            status: "prepared",
            receipt_status: "current",
            manager_submission_status: "decision_recorded",
            manager_decision: decision,
            receipt_observed_at: "2026-10-10T12:30:00Z",
          }}
          busy={false}
          onRefresh={vi.fn()}
        />
      );
      const status = screen.getByRole("status");
      expect(within(status).getByText("Decision recorded")).toBeInTheDocument();
      const label = {
        approved: "Approved",
        rejected: "Rejected",
        changes_requested: "Changes requested",
      }[decision];
      expect(within(status).getByText(label)).toBeInTheDocument();
      expect(within(status).getByText(/Last observed: 2026-10-10/)).toBeInTheDocument();
    }
  );

  it.each(["unavailable", "stale", "not_found", "unauthorized"] as const)(
    "labels a retained decision as historical after a %s read",
    (receipt_status) => {
      render(
        <PortalHandoffStatus
          handoff={{
            status: "prepared",
            receipt_status,
            manager_submission_status: "unknown",
            manager_decision: null,
            last_manager_decision: "approved",
          }}
          busy={false}
          onRefresh={vi.fn()}
        />
      );
      expect(screen.getByText("Last recorded manager decision")).toBeInTheDocument();
      expect(screen.queryByText("Manager decision")).toBeNull();
      expect(screen.getByText("Approved")).toBeInTheDocument();
      expect(
        screen.getByText(
          receipt_status === "stale" ? /receipt is stale/ : /Current receipt unavailable/
        )
      ).toBeInTheDocument();
    }
  );

  it("allows a fresh observation and disables it while busy", async () => {
    const onRefresh = vi.fn();
    const page = render(
      <PortalHandoffStatus handoff={{ status: "prepared" }} busy={false} onRefresh={onRefresh} />
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "Refresh approver status" }));
    expect(onRefresh).toHaveBeenCalledOnce();
    page.rerender(
      <PortalHandoffStatus handoff={{ status: "prepared" }} busy onRefresh={onRefresh} />
    );
    expect(screen.getByRole("button", { name: "Refresh approver status" })).toBeDisabled();
  });
});
