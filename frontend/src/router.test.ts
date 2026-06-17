import { beforeEach, describe, expect, it, vi } from "vitest";
import type { LoaderFunctionArgs } from "react-router-dom";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    createBrowserRouter: vi.fn(() => ({})),
  };
});

vi.mock("./api/auth", () => ({
  fetchCurrentSession: vi.fn(),
}));

vi.mock("./api/health", () => ({
  fetchHealthStatus: vi.fn(),
}));

vi.mock("./api/trips", () => ({
  fetchTrip: vi.fn().mockResolvedValue({ trip_id: "trip-1" }),
  fetchTripScenarioHistory: vi.fn().mockResolvedValue({
    saved_scenarios: [],
    planning_history: [],
    planning_sessions: [],
  }),
  fetchTrips: vi.fn().mockResolvedValue([{ trip_id: "trip-1" }]),
}));

vi.mock("./api/workspace", () => ({
  fetchWorkspace: vi.fn().mockResolvedValue({
    trip_record: { trip: { trip_id: "trip-1" } },
    planner_panel_state: {
      trip: { trip_id: "trip-1" },
    },
  }),
}));

import { ApiClientError } from "./lib/api/errors";
import {
  authPageLoader,
  appRoutes,
  protectedTripDetailLoader,
  protectedTripsLoader,
  protectedWorkspaceLoader,
  rootLoader,
} from "./router";

function loaderArgs(
  url: string,
  params: LoaderFunctionArgs["params"] = {}
): LoaderFunctionArgs {
  return {
    params,
    request: new Request(url),
    context: undefined,
    url: new URL(url),
    pattern: "",
  };
}

describe("router auth loaders", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("configures the root route with the v7 hydration fallback", async () => {
    vi.resetModules();
    const { createBrowserRouter } = await import("react-router-dom");
    vi.mocked(createBrowserRouter).mockClear();

    await import("./router");

    expect(appRoutes[0]?.hydrateFallbackElement).toBeTruthy();
    expect(createBrowserRouter).toHaveBeenCalledWith(expect.any(Array));
  });

  it("restores the signed-in session during app bootstrap", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    const { fetchHealthStatus } = await import("./api/health");
    vi.mocked(fetchHealthStatus).mockResolvedValueOnce({
      service: "trip-planner",
      status: "ok",
      environment: "test",
      version: "dev",
    });
    vi.mocked(fetchCurrentSession).mockResolvedValueOnce({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    await expect(
      rootLoader(loaderArgs("http://localhost/"))
    ).resolves.toEqual({
      session: {
        user: {
          user_id: "user:test",
          email: "owner@example.com",
          display_name: "Owner",
        },
      },
    });
    expect(vi.mocked(fetchHealthStatus).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(fetchCurrentSession).mock.invocationCallOrder[0]
    );
  });

  it("surfaces backend startup failure before the auth session lookup", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    const { fetchHealthStatus } = await import("./api/health");
    const startupError = new ApiClientError("The backend startup check failed.", {
      path: "/api/health",
      status: 504,
      statusText: "Gateway Timeout",
    });
    vi.mocked(fetchHealthStatus).mockRejectedValueOnce(startupError);

    await expect(
      rootLoader(loaderArgs("http://localhost/"))
    ).rejects.toBe(startupError);

    expect(fetchCurrentSession).not.toHaveBeenCalled();
  });

  it("keeps auth pages open when no cookie-backed session exists", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    const { fetchHealthStatus } = await import("./api/health");
    vi.mocked(fetchHealthStatus).mockResolvedValueOnce({
      service: "trip-planner",
      status: "ok",
      environment: "test",
      version: "dev",
    });
    vi.mocked(fetchCurrentSession).mockRejectedValueOnce(
      new ApiClientError("No active planner session was found.", {
        path: "/api/auth/session",
        status: 401,
        statusText: "Unauthorized",
      })
    );

    await expect(
      authPageLoader(loaderArgs("http://localhost/login"))
    ).resolves.toBeNull();
  });

  it("reuses the same session lookup within a navigation", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    const { fetchHealthStatus } = await import("./api/health");
    vi.mocked(fetchHealthStatus).mockResolvedValueOnce({
      service: "trip-planner",
      status: "ok",
      environment: "test",
      version: "dev",
    });
    vi.mocked(fetchCurrentSession).mockResolvedValue({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    const request = new Request("http://localhost/login");

    const results = await Promise.allSettled([
      rootLoader(loaderArgs(request.url)),
      authPageLoader(loaderArgs(request.url)),
    ]);

    expect(results[0]).toMatchObject({
      status: "fulfilled",
      value: {
        session: {
          user: {
            user_id: "user:test",
          },
        },
      },
    });
    expect(results[1]).toMatchObject({
      status: "rejected",
      reason: expect.any(Response),
    });
    expect(fetchCurrentSession).toHaveBeenCalledTimes(1);
    expect(fetchHealthStatus).toHaveBeenCalledTimes(1);
  });

  it("redirects protected workspace routes back to sign-in when the session check fails", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    const { fetchHealthStatus } = await import("./api/health");
    vi.mocked(fetchHealthStatus).mockResolvedValueOnce({
      service: "trip-planner",
      status: "ok",
      environment: "test",
      version: "dev",
    });
    vi.mocked(fetchCurrentSession).mockRejectedValueOnce(
      new ApiClientError("No active planner session was found.", {
        path: "/api/auth/session",
        status: 401,
        statusText: "Unauthorized",
      })
    );

    let response: Response | undefined;
    try {
      await protectedWorkspaceLoader({
        ...loaderArgs("http://localhost/workspace/trip-1", { tripId: "trip-1" }),
      });
    } catch (error) {
      response = error as Response;
    }

    expect(response).toBeInstanceOf(Response);
    expect(response?.status).toBe(302);
    expect(response?.headers.get("Location")).toBe("/login?next=%2Fworkspace%2Ftrip-1");
  });

  it("loads workspace data and persisted trips for signed-in users", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    const { fetchHealthStatus } = await import("./api/health");
    const { fetchTrips } = await import("./api/trips");
    const { fetchWorkspace } = await import("./api/workspace");
    vi.mocked(fetchHealthStatus).mockResolvedValueOnce({
      service: "trip-planner",
      status: "ok",
      environment: "test",
      version: "dev",
    });
    vi.mocked(fetchCurrentSession).mockResolvedValueOnce({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    const result = await protectedWorkspaceLoader(
      loaderArgs("http://localhost/workspace/trip-1", { tripId: "trip-1" })
    );

    expect(fetchWorkspace).toHaveBeenCalledWith("trip-1");
    expect(fetchTrips).toHaveBeenCalledTimes(1);
    await expect(result.workspace).resolves.toEqual({
      trip_record: { trip: { trip_id: "trip-1" } },
      planner_panel_state: {
        trip: { trip_id: "trip-1" },
      },
    });
    await expect(result.trips).resolves.toEqual([{ trip_id: "trip-1" }]);
  });

  it("loads the persisted trip list for signed-in users", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    const { fetchHealthStatus } = await import("./api/health");
    const { fetchTrips } = await import("./api/trips");
    vi.mocked(fetchHealthStatus).mockResolvedValueOnce({
      service: "trip-planner",
      status: "ok",
      environment: "test",
      version: "dev",
    });
    vi.mocked(fetchCurrentSession).mockResolvedValueOnce({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    const result = await protectedTripsLoader(loaderArgs("http://localhost/trips"));

    expect(fetchTrips).toHaveBeenCalledTimes(1);
    await expect(result.trips).resolves.toEqual([{ trip_id: "trip-1" }]);
  });

  it("loads a persisted trip detail for signed-in users", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    const { fetchHealthStatus } = await import("./api/health");
    const { fetchTrip, fetchTripScenarioHistory } = await import("./api/trips");
    vi.mocked(fetchHealthStatus).mockResolvedValueOnce({
      service: "trip-planner",
      status: "ok",
      environment: "test",
      version: "dev",
    });
    vi.mocked(fetchCurrentSession).mockResolvedValueOnce({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    const result = await protectedTripDetailLoader(
      loaderArgs("http://localhost/trips/trip-1", { tripId: "trip-1" })
    );

    expect(fetchTrip).toHaveBeenCalledWith("trip-1");
    expect(fetchTripScenarioHistory).toHaveBeenCalledWith("trip-1");
    await expect(result.tripDetail).resolves.toEqual({
      trip: { trip_id: "trip-1" },
      scenarioHistory: {
        saved_scenarios: [],
        planning_history: [],
        planning_sessions: [],
      },
    });
  });
});
