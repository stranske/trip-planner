import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLoaderData } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TripsPage } from "./TripsPage";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useLoaderData: vi.fn(),
  };
});

const mockedUseLoaderData = vi.mocked(useLoaderData);

describe("TripsPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders saved trip cards from the loader payload", async () => {
    mockedUseLoaderData.mockReturnValue({
      trips: Promise.resolve([
        {
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
            primary_regions: ["Kyoto", "Osaka"],
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
        },
      ]),
    });

    render(
      <MemoryRouter>
        <TripsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Kyoto Spring" })).toBeInTheDocument();
    });

    expect(screen.getByText("Food and gardens")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open trip detail" })).toHaveAttribute(
      "href",
      "/trips/trip-kyoto-123abc"
    );
  });
});
