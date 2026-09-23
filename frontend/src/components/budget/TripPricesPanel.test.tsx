/**
 * Drives the panel the way a traveller does: type a figure, save it, see it attributed.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TripPricesState } from "../../api/workspace";
import { TripPricesPanel } from "./TripPricesPanel";

afterEach(() => {
  cleanup();
});

const EMPTY: TripPricesState = {
  components: [
    { component: "transport", label: "Flights and ground travel", currency: "USD", typical_amount: null, note: "", price_source: null },
    { component: "lodging", label: "Accommodation", currency: "USD", typical_amount: null, note: "", price_source: null },
  ],
  total: null,
  priced_component_count: 0,
  unpriced_component_count: 2,
};

const PRICED: TripPricesState = {
  components: [
    {
      component: "transport",
      label: "Flights and ground travel",
      currency: "USD",
      typical_amount: 486,
      note: "United.com",
      price_source: { kind: "manual", attributed_to: "Dana Chen", captured_at: "2026-09-21T10:00:00+00:00" },
    },
    { component: "lodging", label: "Accommodation", currency: "USD", typical_amount: null, note: "", price_source: null },
  ],
  total: {
    typical_amount: 486,
    currency: "USD",
    price_source: { kind: "manual", attributed_to: "Dana Chen", captured_at: "2026-09-21T10:00:00+00:00" },
  },
  priced_component_count: 1,
  unpriced_component_count: 1,
};

describe("TripPricesPanel", () => {
  it("shows no figure, and says what would supply one", () => {
    render(<TripPricesPanel prices={EMPTY} busy={false} errorMessage={null} onSave={vi.fn()} />);

    expect(screen.getByTestId("trip-prices-total")).toHaveTextContent("Not priced");
    expect(screen.getByTestId("trip-prices-total").textContent).not.toMatch(/\$0\b/);
    // Blocking quantity and drainable quantity in the same place.
    expect(screen.getByTestId("trip-prices-unpriced-count")).toHaveTextContent("2 of 2");
    expect(screen.getByTestId("trip-prices-unpriced-count")).toHaveTextContent("enter a figure");
  });

  it("sends the typed amount for the right component", async () => {
    const onSave = vi.fn();
    render(<TripPricesPanel prices={EMPTY} busy={false} errorMessage={null} onSave={onSave} />);

    fireEvent.change(screen.getByLabelText("Flights and ground travel"), {
      target: { value: "486" },
    });
    fireEvent.change(screen.getByLabelText("Where the Flights and ground travel figure came from"), {
      target: { value: "United.com" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Save" })[0]!);

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith("transport", 486, "United.com", {
        lowestAmount: null,
        evidenceAttested: false,
        cabinClass: null,
        flightHours: null,
      });
    });
  });

  it("names who entered a saved figure", () => {
    render(<TripPricesPanel prices={PRICED} busy={false} errorMessage={null} onSave={vi.fn()} />);

    expect(screen.getByTestId("trip-prices-total")).toHaveTextContent("$486");
    expect(screen.getByTestId("trip-prices-total")).toHaveTextContent("Dana Chen");
    expect(screen.getByTestId("trip-price-source-transport")).toHaveTextContent(
      "Entered by Dana Chen on September 21, 2026"
    );
    expect(screen.getByTestId("trip-price-source-lodging")).toHaveTextContent(
      "No source has priced this yet."
    );
  });

  it("withdraws a figure entirely rather than zeroing it", async () => {
    const onSave = vi.fn();
    render(<TripPricesPanel prices={PRICED} busy={false} errorMessage={null} onSave={onSave} />);

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() => {
      // null withdraws; 0 would assert the leg is free, which nobody said.
      expect(onSave).toHaveBeenCalledWith("transport", null, "");
    });
  });

  it("clearing the field withdraws rather than saving zero", async () => {
    const onSave = vi.fn();
    render(<TripPricesPanel prices={PRICED} busy={false} errorMessage={null} onSave={onSave} />);

    fireEvent.change(screen.getByLabelText("Flights and ground travel"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Update" }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith("transport", null, "United.com", {
        lowestAmount: null,
        evidenceAttested: false,
        cabinClass: null,
        flightHours: null,
      });
    });
  });

  it("sends the lowest fare and the evidence attestation with the flight price", async () => {
    // TPP's fare rules fail when either is absent, so without these approval was blocked
    // whatever the fare. Both are the traveller's own statement.
    const onSave = vi.fn();
    render(<TripPricesPanel prices={EMPTY} busy={false} errorMessage={null} onSave={onSave} />);

    fireEvent.change(screen.getByLabelText("Flights and ground travel"), { target: { value: "486" } });
    fireEvent.change(screen.getByLabelText("Lowest fare you found for the same journey"), {
      target: { value: "470" },
    });
    fireEvent.click(
      screen.getByLabelText("I have a screenshot or other fare evidence to give my approver")
    );
    fireEvent.change(screen.getByLabelText("Cabin booked"), { target: { value: "economy" } });
    fireEvent.change(screen.getByLabelText("Longest flight, in hours"), { target: { value: "4.5" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Save" })[0]!);

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith("transport", 486, "", {
        lowestAmount: 470,
        evidenceAttested: true,
        cabinClass: "economy",
        flightHours: 4.5,
      });
    });
  });

  it("offers fare detail only on the flights row", () => {
    render(<TripPricesPanel prices={EMPTY} busy={false} errorMessage={null} onSave={vi.fn()} />);
    expect(screen.getAllByLabelText("Lowest fare you found for the same journey")).toHaveLength(1);
  });
});
