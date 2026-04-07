import { describe, expect, it } from "vitest";

import { fetchHealthStatus } from "../api/health";
import { fetchWorkspace } from "../api/workspace";

describe("runtime smoke", () => {
  it("connects the frontend client to the live backend runtime", async () => {
    expect(import.meta.env.VITE_API_BASE_URL).toBeTruthy();

    const health = await fetchHealthStatus();
    const workspace = await fetchWorkspace("trip-leisure-kyoto-draft");

    expect(health).toMatchObject({
      service: "trip-planner-api",
      status: "ok",
    });
    expect(workspace.trip_record.trip.trip_id).toBe("trip-leisure-kyoto-draft");
    expect(workspace.scenario_search.scenarios[0]?.scenario_summary.route_sequence).toEqual([
      "kyoto",
      "uji",
      "kyoto",
    ]);
  });
});
