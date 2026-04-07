export type HealthStatus = {
  service: string;
  status: string;
  environment: string;
  version: string;
};

export async function fetchHealthStatus(): Promise<HealthStatus> {
  const response = await fetch("/api/health");
  if (!response.ok) {
    throw new Error(`Health request failed with status ${response.status}`);
  }
  return (await response.json()) as HealthStatus;
}
