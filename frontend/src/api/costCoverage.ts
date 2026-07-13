import { fetchJson } from "../lib/api/client";

export type CostCoverageStatus =
  | "needs_input"
  | "research_ready"
  | "researched"
  | "estimated"
  | "evidenced"
  | "complete"
  | "not_applicable";

export type ResearchSource = {
  title: string;
  url: string;
};

export type ResearchOption = {
  name: string;
  unit_rate: number | null;
  unit: string;
  estimated_total: number | null;
  notes: string;
  source_url: string;
  details?: Record<string, string | number | boolean | null>;
};

export type CostCoverageRequirement = {
  code: string;
  category: string;
  title: string;
  summary: string;
  collection_mode: "automatic" | "researchable" | "traveler";
  evidence_kind: string;
  required_inputs: string[];
  output_fields: string[];
  research_prompt?: string | null;
  policy_reference?: string | null;
  status: CostCoverageStatus;
  inputs: Record<string, string>;
  missing_inputs: string[];
  estimate_amount: number | null;
  currency: string;
  note: string;
  source_url: string;
  research: {
    status: string;
    summary: string;
    options: ResearchOption[];
    sources: ResearchSource[];
    researched_at: string;
    model: string | null;
  } | null;
  selected_option: ResearchOption | null;
  updated_at: string | null;
};

export type CostCoverageResponse = {
  trip_id: string;
  contract_version: string;
  source_status: string;
  summary: {
    requirement_count: number;
    resolved_count: number;
    research_offer_count: number;
    ready_for_handoff: boolean;
    headline: string;
  };
  requirements: CostCoverageRequirement[];
  research_notice?: {
    status: string;
    missing_inputs: string[];
    message: string;
  } | null;
};

export function fetchCostCoverage(tripId: string): Promise<CostCoverageResponse> {
  return fetchJson<CostCoverageResponse>({
    path: `/api/workspace/${tripId}/cost-coverage`,
    credentials: "include",
  });
}

export function researchCostCoverage(
  tripId: string,
  requirementCode: string,
  inputs: Record<string, string>
): Promise<CostCoverageResponse> {
  return fetchJson<CostCoverageResponse>({
    path: `/api/workspace/${tripId}/cost-coverage/${requirementCode}/research`,
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs }),
  });
}

export function updateCostCoverage(
  tripId: string,
  requirementCode: string,
  payload: {
    status?: CostCoverageStatus;
    estimate_amount?: number;
    currency?: string;
    note?: string;
    source_url?: string;
    inputs?: Record<string, string>;
    selected_option?: ResearchOption;
  }
): Promise<CostCoverageResponse> {
  return fetchJson<CostCoverageResponse>({
    path: `/api/workspace/${tripId}/cost-coverage/${requirementCode}`,
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
