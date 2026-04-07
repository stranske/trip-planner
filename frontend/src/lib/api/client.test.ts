import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchJson } from "./client";
import { ApiClientError } from "./errors";

describe("fetchJson", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns typed JSON payloads from the shared client", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({ service: "trip-planner-api" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchJson<{ service: string }>({ path: "/api/health" })).resolves.toEqual({
      service: "trip-planner-api",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      })
    );
  });

  it("throws an ApiClientError when the response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        clone() {
          return this;
        },
        json: async () => ({ detail: "Backend warming up" }),
        text: async () => "Backend warming up",
      })
    );

    await expect(fetchJson({ path: "/api/health" })).rejects.toMatchObject({
      name: "ApiClientError",
      message: "Backend warming up",
      path: "/api/health",
      status: 503,
    } satisfies Partial<ApiClientError>);
  });
});
