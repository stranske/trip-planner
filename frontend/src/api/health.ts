import { fetchJson } from "../lib/api/client";

export type HealthStatus = {
  service: string;
  status: string;
  environment: string;
  version: string;
  /** Database readiness as last observed; absent from backends older than issue 1851. */
  database?: { ready: boolean; reason: string | null; checked_at: string | null } | null;
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
