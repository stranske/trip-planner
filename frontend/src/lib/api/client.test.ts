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

    const request = fetchMock.mock.calls[0]?.[1];

    expect(fetchMock).toHaveBeenCalledWith("/api/health", expect.any(Object));
    expect(request?.headers).toBeInstanceOf(Headers);
    expect((request?.headers as Headers).get("Accept")).toBe("application/json");
  });

  it("preserves custom headers passed as a Headers instance", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const headers = new Headers({ Authorization: "Bearer token" });

    await fetchJson<{ ok: boolean }>({ path: "/api/health", headers });

    const request = fetchMock.mock.calls[0]?.[1];

    expect(request?.headers).toBeInstanceOf(Headers);
    expect((request?.headers as Headers).get("Accept")).toBe("application/json");
    expect((request?.headers as Headers).get("Authorization")).toBe("Bearer token");
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
