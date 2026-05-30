import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchJson } from "./client";
import { ApiClientError } from "./errors";

describe("fetchJson", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("returns typed JSON payloads from the shared client", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      text: async () => JSON.stringify({ service: "trip-planner-api" }),
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
      text: async () => JSON.stringify({ ok: true }),
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

  it("allows successful no-content responses for mutation endpoints", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        statusText: "No Content",
        text: async () => "",
      })
    );

    await expect(fetchJson<void>({ path: "/api/trips/trip-1", method: "DELETE" })).resolves.toBeUndefined();
  });

  it("resolves request URLs against VITE_API_BASE_URL when configured", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test/base/");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      text: async () => JSON.stringify({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchJson<{ ok: boolean }>({ path: "/api/health" })).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledWith("https://api.example.test/api/health", expect.any(Object));
  });

  it("reports the resolved request URL in ApiClientError details", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test/base/");
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
      path: "https://api.example.test/api/health",
      status: 503,
    } satisfies Partial<ApiClientError>);
  });

  it("retries the first health probe when the backend is waking up", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 502,
        statusText: "Bad Gateway",
        clone() {
          return this;
        },
        json: async () => ({ detail: "Backend warming up" }),
        text: async () => "Backend warming up",
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        text: async () => JSON.stringify({ status: "ok" }),
      });
    vi.stubGlobal("fetch", fetchMock);

    const request = fetchJson<{ status: string }>({ path: "/api/health" });
    await vi.advanceTimersByTimeAsync(250);

    await expect(request).resolves.toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("stops after the bounded retry budget for health probes", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
      clone() {
        return this;
      },
      json: async () => ({ detail: "Backend warming up" }),
      text: async () => "Backend warming up",
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = fetchJson({ path: "/api/health" });
    // Attach the rejection expectation before advancing timers so the
    // settled-during-advance rejection is observed in-band instead of
    // surfacing as an unhandled rejection while the timers flush.
    const rejection = expect(request).rejects.toMatchObject({
      name: "ApiClientError",
      status: 503,
    } satisfies Partial<ApiClientError>);
    await vi.advanceTimersByTimeAsync(250 + 500);

    await rejection;
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("aborts a hung health probe and consumes the retry budget", async () => {
    vi.useFakeTimers();
    // Never resolve unless the request is aborted; the bounded timeout must
    // be what drives the retry budget so a hanging backend cannot pend forever.
    const fetchMock = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("The operation was aborted.", "AbortError"));
          });
        })
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = fetchJson({ path: "/api/health" });
    const rejection = expect(request).rejects.toMatchObject({
      name: "AbortError",
    });
    // Three 5s timeouts plus the two inter-attempt retry delays.
    await vi.advanceTimersByTimeAsync(3 * 5000 + 250 + 500);

    await rejection;
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not retry non-health API requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      clone() {
        return this;
      },
      json: async () => ({ detail: "Backend warming up" }),
      text: async () => "Backend warming up",
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchJson({ path: "/api/trips" })).rejects.toMatchObject({
      name: "ApiClientError",
      status: 502,
    } satisfies Partial<ApiClientError>);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
