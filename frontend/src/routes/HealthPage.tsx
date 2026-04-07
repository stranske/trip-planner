import { useEffect, useState } from "react";

import { fetchHealthStatus, type HealthStatus } from "../api/health";

type ViewState =
  | { kind: "loading" }
  | { kind: "ready"; health: HealthStatus }
  | { kind: "error"; message: string };

export function HealthPage() {
  const [state, setState] = useState<ViewState>({ kind: "loading" });

  useEffect(() => {
    let active = true;

    fetchHealthStatus()
      .then((health) => {
        if (active) {
          setState({ kind: "ready", health });
        }
      })
      .catch((error: Error) => {
        if (active) {
          setState({ kind: "error", message: error.message });
        }
      });

    return () => {
      active = false;
    };
  }, []);

  if (state.kind === "loading") {
    return (
      <section className="status-card">
        <p className="status-label">Backend status</p>
        <h2>Checking the live runtime</h2>
        <p>Fetching the FastAPI health endpoint.</p>
      </section>
    );
  }

  if (state.kind === "error") {
    return (
      <section className="status-card status-card-error">
        <p className="status-label">Backend status</p>
        <h2>Health request failed</h2>
        <p>{state.message}</p>
      </section>
    );
  }

  return (
    <section className="status-card">
      <p className="status-label">Backend status</p>
      <h2>{state.health.service}</h2>
      <dl className="status-grid">
        <div>
          <dt>State</dt>
          <dd>{state.health.status}</dd>
        </div>
        <div>
          <dt>Environment</dt>
          <dd>{state.health.environment}</dd>
        </div>
        <div>
          <dt>Version</dt>
          <dd>{state.health.version}</dd>
        </div>
      </dl>
    </section>
  );
}
