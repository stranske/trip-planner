import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PolicyPanel } from "./PolicyPanel";

describe("PolicyPanel", () => {
  it("offers an enabled action when no approval packet exists", () => {
    const onPrepare = vi.fn();

    render(<PolicyPanel approvalPacketContent={null} noPacketAction={{ onPrepare }} />);

    expect(screen.getByRole("heading", { name: "No approval packet yet" })).toBeInTheDocument();
    const action = screen.getByRole("button", { name: "Prepare approval packet" });
    expect(action).toBeEnabled();

    fireEvent.click(action);
    expect(onPrepare).toHaveBeenCalledOnce();
  });
});
