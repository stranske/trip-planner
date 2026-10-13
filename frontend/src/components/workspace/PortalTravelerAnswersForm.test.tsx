import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PortalTravelerAnswersForm } from "./PortalTravelerAnswersForm";

describe("Portal traveler answers", () => {
  it("reopens the stored immutable handoff without replacement answers", async () => {
    const submit = vi.fn();
    render(<PortalTravelerAnswersForm disabled={false} prepared onSubmit={submit} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Reopen approver portal" }));
    expect(submit).toHaveBeenCalledWith();
    expect(screen.queryByLabelText("Destination ZIP")).toBeNull();
  });
  it("collects explicit answers and omits optional unknown facts", async () => {
    const submit = vi.fn();
    render(<PortalTravelerAnswersForm disabled={false} onSubmit={submit} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Send to my approver" }));
    expect(submit).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Destination ZIP"), "20001");
    await user.type(screen.getByLabelText("Booking date"), "2026-12-01");
    await user.selectOptions(screen.getByLabelText("Fare evidence attached"), "false");
    await user.click(screen.getByRole("button", { name: "Send to my approver" }));
    expect(submit).toHaveBeenCalledWith({ destination_zip: "20001", booking_date: "2026-12-01", fare_evidence_attached: "false" });
  });
});
