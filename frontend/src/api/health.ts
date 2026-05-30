import { fetchJson } from "../lib/api/client";

export type HealthStatus = {
  service: string;
  status: string;
  environment: string;
  version: string;
};

let inFlightHealthProbe: Promise<HealthStatus> | null = null;

export async function fetchHealthStatus(): Promise<HealthStatus> {
  if (inFlightHealthProbe) {
    return inFlightHealthProbe;
  }

  inFlightHealthProbe = fetchJson<HealthStatus>({ path: "/api/health" }).finally(() => {
    inFlightHealthProbe = null;
  });

  return inFlightHealthProbe;
}
