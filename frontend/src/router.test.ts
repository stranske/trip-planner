import { beforeEach, describe, expect, it, vi } from "vitest";

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
  protectedTripDetailLoader,
  protectedTripsLoader,
  protectedWorkspaceLoader,
  rootLoader,
} from "./router";

describe("router auth loaders", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("restores the signed-in session during app bootstrap", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    vi.mocked(fetchCurrentSession).mockResolvedValueOnce({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    await expect(
      rootLoader({
        params: {},
        request: new Request("http://localhost/"),
        context: undefined,
      })
    ).resolves.toEqual({
      session: {
        user: {
          user_id: "user:test",
          email: "owner@example.com",
          display_name: "Owner",
        },
      },
    });
  });

  it("keeps auth pages open when no cookie-backed session exists", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    vi.mocked(fetchCurrentSession).mockRejectedValueOnce(
      new ApiClientError("No active planner session was found.", {
        path: "/api/auth/session",
        status: 401,
        statusText: "Unauthorized",
      })
    );

    await expect(
      authPageLoader({
        params: {},
        request: new Request("http://localhost/login"),
        context: undefined,
      })
    ).resolves.toBeNull();
  });

  it("reuses the same session lookup within a navigation", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    vi.mocked(fetchCurrentSession).mockResolvedValue({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    const request = new Request("http://localhost/login");

    const results = await Promise.allSettled([
      rootLoader({ params: {}, request, context: undefined }),
      authPageLoader({ params: {}, request, context: undefined }),
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
  });

  it("redirects protected workspace routes back to sign-in when the session check fails", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
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
        params: { tripId: "trip-1" },
        request: new Request("http://localhost/workspace/trip-1"),
        context: undefined,
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
    const { fetchTrips } = await import("./api/trips");
    const { fetchWorkspace } = await import("./api/workspace");
    vi.mocked(fetchCurrentSession).mockResolvedValueOnce({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    const result = await protectedWorkspaceLoader({
      params: { tripId: "trip-1" },
      request: new Request("http://localhost/workspace/trip-1"),
      context: undefined,
    });

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
    const { fetchTrips } = await import("./api/trips");
    vi.mocked(fetchCurrentSession).mockResolvedValueOnce({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    const result = await protectedTripsLoader({
      params: {},
      request: new Request("http://localhost/trips"),
      context: undefined,
    });

    expect(fetchTrips).toHaveBeenCalledTimes(1);
    await expect(result.trips).resolves.toEqual([{ trip_id: "trip-1" }]);
  });

  it("loads a persisted trip detail for signed-in users", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    const { fetchTrip, fetchTripScenarioHistory } = await import("./api/trips");
    vi.mocked(fetchCurrentSession).mockResolvedValueOnce({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    const result = await protectedTripDetailLoader({
      params: { tripId: "trip-1" },
      request: new Request("http://localhost/trips/trip-1"),
      context: undefined,
    });

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
