import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createTrip } from "../api/trips";
import { NewTripPage } from "./NewTripPage";

vi.mock("../api/trips", () => ({
  createTrip: vi.fn(),
}));

const mockedCreateTrip = vi.mocked(createTrip);
const mockedNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
  };
});

describe("NewTripPage", () => {
  afterEach(() => {
    cleanup();
    mockedCreateTrip.mockReset();
    mockedNavigate.mockReset();
  });

  it("creates a trip and navigates to the detail route", async () => {
    mockedCreateTrip.mockResolvedValue({
      trip_id: "trip-kyoto-123abc",
      user_id: "user:test",
      title: "Kyoto Spring",
      summary: "Food and gardens",
      mode: "leisure",
      status: "draft",
      trip_frame: {
        start_date: "2026-04-20",
        end_date: "2026-04-26",
        duration_days: 7,
        primary_regions: ["Kyoto"],
        traveler_party: { kind: "solo", traveler_count: 1, notes: "" },
      },
      profile_refs: {
        leisure_profile_id: "profile:trip-kyoto-123abc:leisure",
        business_profile_id: null,
      },
      artifacts: {
        objective_id: null,
        option_set_ids: [],
        itinerary_state_id: null,
        budget_state_id: null,
        policy_state_id: null,
      },
    });

    render(
      <MemoryRouter>
        <NewTripPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Kyoto Spring" } });
    fireEvent.change(screen.getByLabelText("Summary"), { target: { value: "Food and gardens" } });
    fireEvent.click(screen.getByRole("button", { name: "Create trip" }));

    await waitFor(() => {
      expect(mockedCreateTrip).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Kyoto Spring",
          summary: "Food and gardens",
          mode: "leisure",
        })
      );
    });
    expect(mockedNavigate).toHaveBeenCalledWith("/trips/trip-kyoto-123abc");
  });
});
