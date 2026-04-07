import { fetchJson } from "../lib/api/client";

export type HealthStatus = {
  service: string;
  status: string;
  environment: string;
  version: string;
};

export async function fetchHealthStatus(): Promise<HealthStatus> {
  return fetchJson<HealthStatus>({ path: "/api/health" });
}
