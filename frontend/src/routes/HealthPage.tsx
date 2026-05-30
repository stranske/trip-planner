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
        title: "Checking backend health",
        message: "Running the shared /api/health probe with bounded cold-start retries.",
      }}
      error={{
        label: "Backend status",
        title: "Backend health check failed",
        message: "The /api/health probe exhausted its cold-start retry budget before succeeding.",
      }}
    >
      {(resolvedHealth) => <HealthStatusCard health={resolvedHealth} />}
    </AsyncRouteContent>
  );
}
