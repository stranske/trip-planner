import { describe, expect, it, vi } from "vitest";

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

vi.mock("./api/workspace", () => ({
  fetchWorkspace: vi.fn().mockResolvedValue({ trip_record: { trip: { trip_id: "trip-1" } } }),
}));

import { ApiClientError } from "./lib/api/errors";
import { authPageLoader, protectedWorkspaceLoader, rootLoader } from "./router";

describe("router auth loaders", () => {
  it("restores the signed-in session during app bootstrap", async () => {
    const { fetchCurrentSession } = await import("./api/auth");
    vi.mocked(fetchCurrentSession).mockResolvedValueOnce({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    await expect(rootLoader()).resolves.toEqual({
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

    await expect(authPageLoader()).resolves.toBeNull();
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
});
