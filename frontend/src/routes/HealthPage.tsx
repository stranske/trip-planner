import { useLoaderData } from "react-router-dom";

import { AsyncRouteContent } from "../lib/routes/AsyncRouteContent";
import { createDeferredLoader } from "../lib/routes/loaders";
import { fetchHealthStatus, type HealthStatus } from "../api/health";

type LoaderData = {
  health: Promise<HealthStatus>;
};

export const healthLoader = createDeferredLoader("health", async () => fetchHealthStatus());

function HealthStatusCard({ health }: { health: HealthStatus }) {
  return (
    <section className="status-card">
      <p className="status-label">Backend status</p>
      <h2>{health.service}</h2>
      <dl className="status-grid">
        <div>
          <dt>State</dt>
          <dd>{health.status}</dd>
        </div>
        <div>
          <dt>Environment</dt>
          <dd>{health.environment}</dd>
        </div>
        <div>
          <dt>Version</dt>
          <dd>{health.version}</dd>
        </div>
      </dl>
    </section>
  );
}

export function HealthPage() {
  const { health } = useLoaderData() as LoaderData;

  return (
    <AsyncRouteContent
      resolve={health}
      loading={{
        label: "Backend status",
        title: "Checking the live runtime",
        message: "Fetching the FastAPI health endpoint.",
      }}
      error={{
        label: "Backend status",
        title: "Health request failed",
        message: "The shared API client could not load backend health.",
      }}
    >
      {(resolvedHealth) => <HealthStatusCard health={resolvedHealth} />}
    </AsyncRouteContent>
  );
}
