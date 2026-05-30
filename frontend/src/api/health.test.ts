import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHealthStatus } from "./health";

describe("fetchHealthStatus", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shares one in-flight /api/health probe across concurrent calls", async () => {
    let resolveFetch: ((value: unknown) => void) | undefined;
    const fetchMock = vi.fn(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        })
    );
    vi.stubGlobal("fetch", fetchMock);

    const requestA = fetchHealthStatus();
    const requestB = fetchHealthStatus();

    resolveFetch?.({
      ok: true,
      status: 200,
      statusText: "OK",
      text: async () =>
        JSON.stringify({
          service: "trip-planner-api",
          status: "ok",
          environment: "local",
          version: "0.1.0",
        }),
    });

    await expect(requestA).resolves.toMatchObject({ status: "ok" });
    await expect(requestB).resolves.toMatchObject({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
