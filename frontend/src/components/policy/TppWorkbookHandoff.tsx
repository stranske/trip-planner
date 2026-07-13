import { useState } from "react";

import {
  fetchCostCoverage,
  type CostCoverageRequirement,
  type CostCoverageResponse,
} from "../../api/costCoverage";
import type { RuntimeScenarioComparison, WorkspaceData } from "../../api/workspace";

type WorkspaceTrip = WorkspaceData["trip_record"]["trip"];
type WorkspaceScenario = RuntimeScenarioComparison["scenarios"][number];

export function buildTppHandoffAnswers(
  trip: WorkspaceTrip,
  scenario: WorkspaceScenario | null,
  coverage: CostCoverageResponse | null = null
): Record<string, string> {
  const eventDates =
    trip.trip_frame.start_date && trip.trip_frame.end_date
      ? `${trip.trip_frame.start_date} - ${trip.trip_frame.end_date}`
      : "";
  const byCode = new Map(
    (coverage?.requirements ?? []).map((requirement) => [requirement.code, requirement])
  );
  const selected = (code: string) => byCode.get(code)?.selected_option ?? null;
  const amount = (requirement: CostCoverageRequirement | undefined) =>
    requirement?.estimate_amount ?? requirement?.selected_option?.estimated_total ?? null;
  const parking = byCode.get("airport_parking");
  const intercity = byCode.get("intercity_transport");
  const lodging = byCode.get("lodging");
  const lodgingOption = selected("lodging");
  const meals = byCode.get("meals_incidentals");
  const mealOption = selected("meals_incidentals") ?? meals?.research?.options[0] ?? null;
  const mealDetails = mealOption?.details ?? {};
  const airportAccess = byCode.get("airport_access");
  const airportAccessDetails = airportAccess?.selected_option?.details ?? {};
  const groundRequirements = ["destination_transfers", "local_mobility"]
    .map((code) => byCode.get(code))
    .filter((item): item is CostCoverageRequirement => item != null);
  const groundEstimate = groundRequirements.reduce(
    (total, requirement) => total + (amount(requirement) ?? 0),
    0
  );
  const detailNumber = (key: string) => {
    const value = airportAccessDetails[key];
    return typeof value === "number" ? value : Number.parseFloat(String(value ?? ""));
  };
  const mileageMiles = detailNumber("reimbursable_miles");
  const mileageCost = detailNumber("mileage_cost");
  const airportRideshare = detailNumber("rideshare_total");
  const destinationGroundEstimate = groundEstimate;
  const totalRideshare =
    (Number.isFinite(airportRideshare) ? airportRideshare : 0) + destinationGroundEstimate;
  const fareOptions = intercity?.research?.options ?? [];
  const comparableLodging = (lodging?.research?.options ?? []).filter(
    (option) => option.name !== lodgingOption?.name
  );
  const sourceNotes = (coverage?.requirements ?? [])
    .filter((requirement) => requirement.source_url || requirement.research?.sources.length)
    .map((requirement) => {
      const urls = (
        requirement.source_url
          ? [requirement.source_url]
          : requirement.research?.sources.slice(0, 3).map((source) => source.url) ?? []
      ).filter((url, index, urls) => Boolean(url) && urls.indexOf(url) === index);
      return `${requirement.title}: ${urls.join(", ")}`;
    });
  const notes = [
    `Prepared from trip-planner trip ${trip.trip_id}.`,
    scenario ? `Selected scenario: ${scenario.title}. ${scenario.route_summary}` : "",
    sourceNotes.length > 0 ? `Planner evidence — ${sourceNotes.join(" | ")}` : "",
  ]
    .filter(Boolean)
    .join(" ");
  return Object.fromEntries(
    Object.entries({
      business_purpose: trip.summary || trip.title,
      city_state: trip.trip_frame.primary_regions.join(", "),
      event_dates: eventDates,
      depart_date: trip.trip_frame.start_date ?? "",
      return_date: trip.trip_frame.end_date ?? "",
      departure_city_airport:
        parking?.inputs.departure_airport ?? intercity?.inputs.departure_airport ?? "",
      return_city_airport: intercity?.inputs.destination_airport ?? "",
      parking_estimate: amount(parking)?.toString() ?? "",
      ground_transport_estimate: groundEstimate > 0 ? groundEstimate.toString() : "",
      ground_transport_pref: [airportAccess, ...groundRequirements]
        .map((requirement) => requirement?.selected_option?.name)
        .filter(Boolean)
        .join("; "),
      "ground_transport.mileage_planned": Number.isFinite(mileageMiles) ? "true" : "",
      "ground_transport.mileage_miles": Number.isFinite(mileageMiles)
        ? mileageMiles.toString()
        : "",
      "ground_transport.mileage_cost": Number.isFinite(mileageCost)
        ? mileageCost.toString()
        : "",
      "ground_transport.rideshare_planned": totalRideshare > 0 ? "true" : "",
      "ground_transport.rideshare_cost": totalRideshare > 0 ? totalRideshare.toString() : "",
      selected_fare: amount(intercity)?.toString() ?? "",
      lowest_fare:
        fareOptions
          .map((option) => option.estimated_total)
          .filter((value): value is number => value != null)
          .sort((left, right) => left - right)[0]?.toString() ?? "",
      fare_evidence_attached: intercity?.source_url ? "true" : "",
      "hotel.name": lodgingOption?.name ?? "",
      "hotel.address": lodgingOption?.details?.address?.toString() ?? "",
      "hotel.nightly_rate": lodgingOption?.unit_rate?.toString() ?? "",
      "hotel.nights": trip.trip_frame.duration_days
        ? Math.max(trip.trip_frame.duration_days - 1, 1).toString()
        : "",
      "hotel.price_compare_notes": lodging?.research?.summary ?? "",
      "comparable_hotels[0].name": comparableLodging[0]?.name ?? "",
      "comparable_hotels[0].nightly_rate": comparableLodging[0]?.unit_rate?.toString() ?? "",
      "comparable_hotels[1].name": comparableLodging[1]?.name ?? "",
      "comparable_hotels[1].nightly_rate": comparableLodging[1]?.unit_rate?.toString() ?? "",
      destination_zip: meals?.inputs.destination_zip ?? "",
      "meal_counts.breakfast": mealDetails.eligible_breakfasts?.toString() ?? "",
      "meal_counts.lunch": mealDetails.eligible_lunches?.toString() ?? "",
      "meal_counts.dinner": mealDetails.eligible_dinners?.toString() ?? "",
      meals_provided:
        typeof mealDetails.meals_provided === "boolean"
          ? String(mealDetails.meals_provided)
          : "",
      meal_per_diem_requested:
        typeof mealDetails.meal_per_diem_requested === "boolean"
          ? String(mealDetails.meal_per_diem_requested)
          : "",
      notes,
    }).filter(([, value]) => value !== "")
  );
}

export function submitTppHandoff(
  portalUrl: string,
  answers: Record<string, string>,
  documentObject: Document = document
) {
  const normalizedBaseUrl = portalUrl.trim().replace(/\/$/, "");
  const handoffUrl = new URL(`${normalizedBaseUrl}/portal/handoff`);
  if (!(["http:", "https:"] as string[]).includes(handoffUrl.protocol)) {
    throw new Error("The TPP portal URL must use HTTP or HTTPS.");
  }
  const form = documentObject.createElement("form");
  form.method = "post";
  form.action = handoffUrl.toString();
  form.hidden = true;
  for (const [name, value] of Object.entries(answers)) {
    const input = documentObject.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.append(input);
  }
  documentObject.body.append(form);
  form.submit();
  form.remove();
}

export function TppWorkbookHandoff({
  trip,
  scenario,
}: {
  trip: WorkspaceTrip;
  scenario: WorkspaceScenario | null;
}) {
  const portalUrl = import.meta.env.VITE_TPP_PORTAL_URL?.trim() ?? "";
  const configured = portalUrl !== "";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleHandoff() {
    setBusy(true);
    setError(null);
    try {
      const coverage = await fetchCostCoverage(trip.trip_id);
      submitTppHandoff(portalUrl, buildTppHandoffAnswers(trip, scenario, coverage));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The cost and evidence record could not be prepared for TPP."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="status-card" data-testid="tpp-workbook-handoff">
      <p className="status-label">Organization workbook</p>
      <h2>Prepare the workplace travel request</h2>
      <p>
        Continue in Travel Plan Permission with this trip prefilled. TPP will collect the
        organization-specific details, validate the request, and generate the Excel workbook.
      </p>
      <p className="muted-copy">
        This handoff creates a review-only browser session. It does not submit the request.
      </p>
      <button
        type="button"
        className="primary-button"
        disabled={!configured || busy}
        onClick={() => void handleHandoff()}
      >
        {busy ? "Preparing evidence handoff…" : "Prepare organization workbook"}
      </button>
      {!configured ? (
        <p className="planner-inline-error" role="status">
          The TPP portal URL is not configured for this runtime.
        </p>
      ) : null}
      {error ? (
        <p className="planner-inline-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
