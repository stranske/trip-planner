import { useLoaderData } from "react-router-dom";

import { AsyncRouteContent } from "../lib/routes/AsyncRouteContent";
import { createDeferredLoader } from "../lib/routes/loaders";
import { fetchHealthStatus, type HealthStatus } from "../api/health";
import { formatInstantDate } from "../lib/dates";

type LoaderData = {
  health: Promise<HealthStatus>;
};

export const healthLoader = createDeferredLoader("health", async () => fetchHealthStatus());

function describeDatabase(database: HealthStatus["database"]): string {
  if (database == null) {
    return "Not reported by this backend";
  }
  if (database.ready) {
    return "Ready";
  }
  const checked = database.checked_at ? ` (last checked ${formatInstantDate(database.checked_at)})` : "";
  return `Not ready: ${database.reason ?? "no reason recorded"}${checked}. Trips cannot be saved or loaded until it is.`;
}

function HealthStatusCard({ health }: { health: HealthStatus }) {
  return (
    <section className="status-card">
      <p className="status-label">Backend status</p>
      <h2>{health.service}</h2>
      <dl className="status-grid">
        <div>
          <dt>State</dt>
          <dd data-testid="health-state">{health.status}</dd>
        </div>
        <div>
          <dt>Database</dt>
          <dd data-testid="health-database">{describeDatabase(health.database)}</dd>
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
