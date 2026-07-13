import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RuntimeScenarioComparison, WorkspaceData } from "../../api/workspace";
import { TppWorkbookHandoff } from "./TppWorkbookHandoff";

const { fetchCostCoverage } = vi.hoisted(() => ({ fetchCostCoverage: vi.fn() }));
vi.mock("../../api/costCoverage", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/costCoverage")>()),
  fetchCostCoverage,
}));

const trip = {
  trip_id: "trip-washington",
  title: "Washington client visit",
  summary: "Client strategy meetings",
  status: "draft",
  mode: "business",
  trip_frame: {
    start_date: "2026-10-14",
    end_date: "2026-10-16",
    duration_days: 3,
    primary_regions: ["Washington DC"],
  },
} satisfies WorkspaceData["trip_record"]["trip"];

const scenario = {
  scenario_id: "scenario-washington",
  title: "Washington runtime bundle",
  route_summary: "DCA to downtown meetings",
} as RuntimeScenarioComparison["scenarios"][number];

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  fetchCostCoverage.mockReset();
});

describe("TppWorkbookHandoff", () => {
  it("posts trip details and sourced estimates to TPP without putting them in the URL", async () => {
    vi.stubEnv("VITE_TPP_PORTAL_URL", "http://127.0.0.1:8765/");
    fetchCostCoverage.mockResolvedValue({
      trip_id: trip.trip_id,
      contract_version: "tpp-intake-requirements/v1",
      source_status: "live_tpp",
      summary: {
        requirement_count: 2,
        resolved_count: 2,
        research_offer_count: 0,
        ready_for_handoff: true,
        headline: "Complete",
      },
      requirements: [
        {
          code: "airport_parking",
          title: "Airport parking",
          inputs: { departure_airport: "STL", parking_days: "3" },
          estimate_amount: 48,
          source_url: "https://www.flystl.com/parking",
          selected_option: {
            name: "Lot C uncovered",
            unit_rate: 12,
            unit: "per day",
            estimated_total: 48,
            notes: "Official airport rate",
            source_url: "https://www.flystl.com/parking",
          },
          research: { sources: [], options: [], summary: "Official parking rates" },
        },
        {
          code: "airport_access",
          title: "Airport access",
          inputs: {
            traveler_residence_address: "803 B Broadway, Jefferson City, MO",
            official_domicile_address: "3236 W Edgewood Dr, Jefferson City, MO 65109",
            departure_airport: "STL",
          },
          estimate_amount: 153.99,
          source_url: "https://www.google.com/maps",
          selected_option: {
            name: "Personal vehicle from home",
            unit_rate: 0.725,
            unit: "mile",
            estimated_total: 153.99,
            notes: "Direct reimbursable route; ordinary commuting excluded.",
            source_url: "https://www.google.com/maps",
            details: {
              reimbursable_miles: 212.4,
              mileage_cost: 153.99,
              route_rule: "Direct route with commuting excluded",
            },
          },
          research: { sources: [], options: [], summary: "Mileage comparison" },
        },
        {
          code: "local_mobility",
          title: "Local transportation",
          inputs: {},
          estimate_amount: 35,
          source_url: "https://new.mta.info/fares",
          selected_option: {
            name: "Subway plus bounded taxi allowance",
            unit_rate: null,
            unit: "trip",
            estimated_total: 35,
            notes: "Transit-first plan",
            source_url: "https://new.mta.info/fares",
          },
          research: { sources: [], options: [], summary: "Transit-first plan" },
        },
        {
          code: "meals_incidentals",
          title: "Meals and incidental allowance",
          inputs: { destination_zip: "20004" },
          estimate_amount: 180,
          source_url: "https://www.gsa.gov/travel/plan-book/per-diem-rates",
          selected_option: {
            name: "Eligible meal allowance",
            unit_rate: null,
            unit: "trip",
            estimated_total: 180,
            notes: "Conference lunches excluded.",
            source_url: "https://www.gsa.gov/travel/plan-book/per-diem-rates",
            details: {
              eligible_breakfasts: 2,
              eligible_lunches: 1,
              eligible_dinners: 2,
              meals_provided: true,
              meal_per_diem_requested: true,
            },
          },
          research: { sources: [], options: [], summary: "Policy meal calculation" },
        },
      ],
    });
    const submittedForms: HTMLFormElement[] = [];
    vi.spyOn(HTMLFormElement.prototype, "submit").mockImplementation(function submit(
      this: HTMLFormElement
    ) {
      submittedForms.push(this);
    });
    render(<TppWorkbookHandoff trip={trip} scenario={scenario} />);

    fireEvent.click(screen.getByRole("button", { name: "Prepare organization workbook" }));

    await waitFor(() => expect(submittedForms).toHaveLength(1));

    const submittedForm = submittedForms[0];
    expect(submittedForm).toBeDefined();
    if (submittedForm == null) {
      throw new Error("Expected the handoff form to be submitted.");
    }
    expect(submittedForm.action).toBe("http://127.0.0.1:8765/portal/handoff");
    expect(submittedForm.method).toBe("post");
    const values = new FormData(submittedForm);
    expect(values.get("business_purpose")).toBe("Client strategy meetings");
    expect(values.get("city_state")).toBe("Washington DC");
    expect(values.get("depart_date")).toBe("2026-10-14");
    expect(values.get("departure_city_airport")).toBe("STL");
    expect(values.get("parking_estimate")).toBe("48");
    expect(values.get("ground_transport_estimate")).toBe("35");
    expect(values.get("ground_transport.mileage_planned")).toBe("true");
    expect(values.get("ground_transport.mileage_miles")).toBe("212.4");
    expect(values.get("ground_transport.mileage_cost")).toBe("153.99");
    expect(values.get("ground_transport.rideshare_cost")).toBe("35");
    expect(values.get("destination_zip")).toBe("20004");
    expect(values.get("meal_counts.breakfast")).toBe("2");
    expect(values.get("meal_counts.lunch")).toBe("1");
    expect(values.get("meal_counts.dinner")).toBe("2");
    expect(values.get("meals_provided")).toBe("true");
    expect(values.get("notes")).toContain("Washington runtime bundle");
    expect(values.get("notes")).toContain("https://www.flystl.com/parking");
    expect(submittedForm.action).not.toContain("Washington");
  });

  it("keeps the handoff disabled until the TPP portal is configured", () => {
    vi.stubEnv("VITE_TPP_PORTAL_URL", "");
    render(<TppWorkbookHandoff trip={trip} scenario={null} />);

    expect(
      screen.getByRole("button", { name: "Prepare organization workbook" })
    ).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("not configured");
  });
});
