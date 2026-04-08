import { describe, expect, it } from "vitest";

import { fetchHealthStatus } from "../api/health";
import type { WorkspaceData } from "../api/workspace";

function resolveApiUrl(path: string): string {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!configuredBaseUrl) {
    throw new Error("VITE_API_BASE_URL must be configured for runtime smoke tests.");
  }

  return new URL(path, `${configuredBaseUrl.replace(/\/+$/, "")}/`).toString();
}

describe("runtime smoke", () => {
  it("connects the frontend client to the live backend runtime", async () => {
    expect(import.meta.env.VITE_API_BASE_URL).toBeTruthy();

    const health = await fetchHealthStatus();
    const signupResponse = await fetch(resolveApiUrl("/api/auth/signup"), {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: `runtime-smoke-${crypto.randomUUID()}@example.com`,
        password: "password123",
        display_name: "Runtime Smoke",
      }),
    });

    expect(signupResponse.ok).toBe(true);
    const sessionCookie = signupResponse.headers.get("set-cookie");
    expect(sessionCookie).toContain("trip_planner_session=");

    const workspaceResponse = await fetch(resolveApiUrl("/api/workspace/trip-leisure-kyoto-draft"), {
      headers: {
        Accept: "application/json",
        Cookie: sessionCookie!.split(";", 1)[0],
      },
    });

    expect(workspaceResponse.ok).toBe(true);
    const workspace = (await workspaceResponse.json()) as WorkspaceData;

    expect(health).toMatchObject({
      service: "trip-planner-api",
      status: "ok",
    });
    expect(workspace.trip_record.trip.trip_id).toBe("trip-leisure-kyoto-draft");
    expect(workspace.scenario_search.scenarios[0]?.scenario_summary.route_sequence).toEqual([
      "dest-city-osaka",
      "dest-city-kyoto",
    ]);
  });
});
