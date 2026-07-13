import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CostCoverageRequirement, CostCoverageResponse } from "../../api/costCoverage";
import { CostEvidencePanel } from "./CostEvidencePanel";

const { fetchCostCoverage, researchCostCoverage, updateCostCoverage } = vi.hoisted(() => ({
  fetchCostCoverage: vi.fn(),
  researchCostCoverage: vi.fn(),
  updateCostCoverage: vi.fn(),
}));

vi.mock("../../api/costCoverage", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/costCoverage")>()),
  fetchCostCoverage,
  researchCostCoverage,
  updateCostCoverage,
}));

const airportParking: CostCoverageRequirement = {
  code: "airport_parking",
  category: "ground_transport",
  title: "Airport parking",
  summary: "Find an official parking option and calculate the total.",
  collection_mode: "researchable" as const,
  evidence_kind: "provider_rate",
  required_inputs: ["departure_airport", "parking_days"],
  output_fields: ["parking_estimate"],
  research_prompt: "Find official airport parking rates.",
  policy_reference: "driving_vs_flying",
  status: "needs_input" as const,
  inputs: { parking_days: "4" },
  missing_inputs: ["departure_airport"],
  estimate_amount: null,
  currency: "USD",
  note: "",
  source_url: "",
  research: null,
  selected_option: null,
  updated_at: null,
};

function responseWith(requirement: CostCoverageRequirement = airportParking): CostCoverageResponse {
  return {
    trip_id: "trip-nyc",
    contract_version: "tpp-intake-requirements/v1",
    source_status: "live_tpp",
    summary: {
      requirement_count: 1,
      resolved_count: requirement.status === "evidenced" ? 1 : 0,
      research_offer_count: requirement.status === "evidenced" ? 0 : 1,
      ready_for_handoff: requirement.status === "evidenced",
      headline: "The planner can research missing trip costs and evidence.",
    },
    requirements: [requirement],
  };
}

afterEach(() => {
  cleanup();
  fetchCostCoverage.mockReset();
  researchCostCoverage.mockReset();
  updateCostCoverage.mockReset();
});

describe("CostEvidencePanel", () => {
  it("asks only for the missing airport and offers to research the parking details", async () => {
    fetchCostCoverage.mockResolvedValue(responseWith());
    researchCostCoverage.mockResolvedValue(responseWith());

    render(<CostEvidencePanel tripId="trip-nyc" />);

    expect(await screen.findByRole("heading", { name: "Airport parking" })).toBeVisible();
    expect(screen.getByLabelText("Departure Airport")).toBeVisible();
    expect(screen.queryByLabelText("Parking Days")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Departure Airport"), { target: { value: "STL" } });
    fireEvent.click(screen.getByRole("button", { name: "Research this for me" }));

    await waitFor(() =>
      expect(researchCostCoverage).toHaveBeenCalledWith("trip-nyc", "airport_parking", {
        parking_days: "4",
        departure_airport: "STL",
      })
    );
  });

  it("shows sourced options and saves the selected estimate for the workbook", async () => {
    const option = {
      name: "Official Lot D",
      unit_rate: 11,
      unit: "per day",
      estimated_total: 44,
      notes: "Official airport economy parking.",
      source_url: "https://www.flystl.com/parking",
    };
    const researched = {
      ...airportParking,
      status: "researched" as const,
      inputs: { parking_days: "4", departure_airport: "STL" },
      missing_inputs: [],
      research: {
        status: "completed",
        summary: "Official airport lots are available.",
        options: [option],
        sources: [{ title: "STL parking", url: option.source_url }],
        researched_at: "2026-07-12T12:00:00Z",
        model: "gpt-5.6-sol",
      },
    };
    fetchCostCoverage.mockResolvedValue(responseWith(researched));
    updateCostCoverage.mockResolvedValue(
      responseWith({
        ...researched,
        status: "evidenced",
        estimate_amount: 44,
        source_url: option.source_url,
        selected_option: option,
      })
    );

    render(<CostEvidencePanel tripId="trip-nyc" />);

    expect(await screen.findByText("$44.00 estimated total")).toBeVisible();
    expect(screen.getByLabelText("Departure Airport")).toHaveValue("STL");
    fireEvent.click(screen.getByRole("button", { name: "Use this estimate" }));

    await waitFor(() =>
      expect(updateCostCoverage).toHaveBeenCalledWith(
        "trip-nyc",
        "airport_parking",
        expect.objectContaining({
          estimate_amount: 44,
          source_url: option.source_url,
          selected_option: option,
        })
      )
    );
    expect(await screen.findByRole("button", { name: "Selected for workbook" })).toBeDisabled();
  });
});
