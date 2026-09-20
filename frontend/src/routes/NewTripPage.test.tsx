import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createTrip } from "../api/trips";
import { NewTripPage, missingTripContext, travelDaysInclusive } from "./NewTripPage";
import { TestMemoryRouter } from "../test/router";

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

function tripResponse() {
  return {
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
  };
}

function renderPage() {
  return render(
    <TestMemoryRouter>
      <NewTripPage />
    </TestMemoryRouter>
  );
}

describe("travelDaysInclusive", () => {
  it("counts travel days inclusively", () => {
    expect(travelDaysInclusive("2026-10-12", "2026-10-15")).toBe(4);
    expect(travelDaysInclusive("2026-10-12", "2026-10-12")).toBe(1);
  });

  it("returns null when the range is unusable", () => {
    expect(travelDaysInclusive("2026-10-15", "2026-10-12")).toBeNull();
    expect(travelDaysInclusive("", "2026-10-12")).toBeNull();
  });
});

describe("missingTripContext", () => {
  it("names every input the planner still needs", () => {
    expect(missingTripContext({ mode: "", purpose: "", destinations: "", startDate: "", endDate: "" })).toEqual([
      "trip type",
      "at least one destination",
      "travel dates",
    ]);
  });

  it("is satisfied once type, destination and dates are supplied", () => {
    expect(
      missingTripContext({
        mode: "business",
        purpose: "Client review",
        destinations: "Chicago, IL",
        startDate: "2026-10-12",
        endDate: "2026-10-15",
      })
    ).toEqual([]);
  });

  it("requires business purpose and a parsed destination", () => {
    expect(missingTripContext({
      mode: "business", purpose: " ", destinations: "; ;", startDate: "2026-10-12", endDate: "2026-10-15",
    })).toEqual(["at least one destination", "a business purpose"]);
  });

  it("treats a reversed date range as missing travel dates", () => {
    expect(missingTripContext({
      mode: "leisure", purpose: "", destinations: "Chicago, IL", startDate: "2026-10-15", endDate: "2026-10-12",
    })).toEqual(["travel dates"]);
  });
});

describe("NewTripPage", () => {
  afterEach(() => {
    cleanup();
    mockedCreateTrip.mockReset();
    mockedNavigate.mockReset();
  });

  it("creates a trip and navigates to the workspace route", async () => {
    mockedCreateTrip.mockResolvedValue(tripResponse());
    renderPage();

    fireEvent.click(screen.getByRole("radio", { name: /Personal trip/ }));
    fireEvent.change(screen.getByLabelText(/Trip name/), { target: { value: "Kyoto Spring" } });
    fireEvent.change(screen.getByLabelText(/What is this trip for\?/), {
      target: { value: "Food and gardens" },
    });
    fireEvent.change(screen.getByLabelText(/Destinations/), { target: { value: "Kyoto; Osaka" } });
    fireEvent.click(screen.getByRole("button", { name: "Create trip" }));

    await waitFor(() => {
      expect(mockedCreateTrip).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Kyoto Spring",
          summary: "Food and gardens",
          mode: "leisure",
          trip_frame: expect.objectContaining({ primary_regions: ["Kyoto", "Osaka"] }),
        })
      );
    });
    expect(mockedNavigate).toHaveBeenCalledWith("/workspace/trip-kyoto-123abc");
  });

  it("preserves a city-state destination as one primary region", async () => {
    mockedCreateTrip.mockResolvedValue(tripResponse());
    renderPage();
    fireEvent.click(screen.getByRole("radio", { name: /Personal trip/ }));
    fireEvent.change(screen.getByLabelText(/Trip name/), { target: { value: "Chicago visit" } });
    fireEvent.change(screen.getByLabelText(/Destinations/), { target: { value: "Chicago, IL" } });
    fireEvent.click(screen.getByRole("button", { name: "Create trip" }));
    await waitFor(() => {
      expect(mockedCreateTrip).toHaveBeenCalledWith(
        expect.objectContaining({ trip_frame: expect.objectContaining({ primary_regions: ["Chicago, IL"] }) })
      );
    });
  });

  it("rejects a whitespace-only trip name before the API call", () => {
    renderPage();
    fireEvent.click(screen.getByRole("radio", { name: /Personal trip/ }));
    fireEvent.change(screen.getByLabelText(/Trip name/), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "Create trip" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/enter a trip name/i);
    expect(mockedCreateTrip).not.toHaveBeenCalled();
  });

  it("requires the traveller to choose a trip type rather than defaulting silently", () => {
    const { container } = renderPage();

    const radios = container.querySelectorAll<HTMLInputElement>('input[name="mode"]');
    expect(radios.length).toBe(2);
    for (const radio of radios) {
      expect(radio.checked).toBe(false);
      expect(radio.required).toBe(true);
    }
  });

  it("keeps every field the create-trip contract sends", () => {
    const { container } = renderPage();

    for (const fieldName of [
      "title",
      "summary",
      "mode",
      "primaryRegions",
      "startDate",
      "endDate",
      "durationDays",
      "travelerKind",
      "travelerCount",
      "travelerNotes",
    ]) {
      expect(container.querySelector(`[name="${fieldName}"]`)).toBeInTheDocument();
    }
  });

  it("groups inputs into labelled sections", () => {
    const { container } = renderPage();

    expect(container.querySelectorAll("fieldset").length).toBeGreaterThanOrEqual(4);
    expect(screen.getByRole("group", { name: "What kind of trip is this?" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "The basics" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "When are you travelling?" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Who is travelling?" })).toBeInTheDocument();
  });

  it("explains each input with inline help", () => {
    const { container } = renderPage();

    // Every section carries guidance rather than a bare label.
    expect(container.querySelectorAll(".field-hint").length).toBeGreaterThanOrEqual(6);
    expect(screen.getByText(/Separate multiple stops with semicolons/)).toBeInTheDocument();
    expect(
      screen.getByText(/decides whether the trip goes through travel policy and approval/)
    ).toBeInTheDocument();
  });

  it("works out trip length from the travel dates", () => {
    const { container } = renderPage();

    fireEvent.change(screen.getByLabelText(/First day of travel/), {
      target: { value: "2026-10-12" },
    });
    fireEvent.change(screen.getByLabelText(/Last day of travel/), {
      target: { value: "2026-10-15" },
    });

    const duration = container.querySelector<HTMLInputElement>('[name="durationDays"]');
    expect(duration?.value).toBe("4");
    expect(screen.getByText(/Worked out from your dates \(4 days\)/)).toBeInTheDocument();
  });

  it("blocks submission when the last day is before the first day", () => {
    renderPage();

    fireEvent.change(screen.getByLabelText(/First day of travel/), {
      target: { value: "2026-10-15" },
    });
    fireEvent.change(screen.getByLabelText(/Last day of travel/), {
      target: { value: "2026-10-12" },
    });

    expect(screen.getByRole("alert")).toHaveTextContent(/last day is before the first day/i);
    expect(screen.getByLabelText(/First day of travel/)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText(/Last day of travel/)).toHaveAttribute("aria-describedby", "dates-error");
    expect(screen.getByRole("button", { name: "Create trip" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Create trip" }));
    expect(mockedCreateTrip).not.toHaveBeenCalled();
  });

  it("tells the traveller what is still missing before options can be assembled", () => {
    renderPage();

    expect(screen.getByText(/Still needed before the planner can assemble options/)).toHaveTextContent(
      /trip type/
    );

    fireEvent.click(screen.getByRole("radio", { name: /Business trip/ }));
    fireEvent.change(screen.getByLabelText(/Destinations/), { target: { value: "Chicago, IL" } });
    fireEvent.change(screen.getByLabelText(/First day of travel/), {
      target: { value: "2026-10-12" },
    });
    fireEvent.change(screen.getByLabelText(/Last day of travel/), {
      target: { value: "2026-10-15" },
    });

    expect(screen.getByText(/Still needed before the planner/)).toHaveTextContent(/business purpose/);
    fireEvent.change(screen.getByLabelText(/Business purpose/), { target: { value: "Client review" } });
    expect(screen.queryByText(/Still needed before the planner/)).not.toBeInTheDocument();
    expect(screen.getByText(/print an approval packet/)).toBeInTheDocument();
  });

  it("asks a business traveller for the purpose an approver will read", () => {
    renderPage();

    fireEvent.click(screen.getByRole("radio", { name: /Business trip/ }));

    expect(screen.getByLabelText(/Business purpose/)).toBeInTheDocument();
    expect(screen.getByText(/Approvers read this first/)).toBeInTheDocument();
  });

  it("blocks submission above eight destinations and identifies the invalid control", () => {
    renderPage();
    const input = screen.getByLabelText(/Destinations/);
    fireEvent.change(input, { target: { value: "A; B; C; D; E; F; G; H; I" } });
    expect(screen.getByRole("alert")).toHaveTextContent(/more than 8 destinations/);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "destinations-hint destinations-error");
    expect(screen.getByRole("button", { name: "Create trip" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Create trip" }));
    expect(mockedCreateTrip).not.toHaveBeenCalled();
  });
});
