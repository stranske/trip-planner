import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { useLoaderData } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HealthPage } from "./HealthPage";
import { TestMemoryRouter } from "../test/router";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useLoaderData: vi.fn(),
  };
});

const mockedUseLoaderData = vi.mocked(useLoaderData);

function renderHealthPage() {
  return render(
    <TestMemoryRouter>
      <HealthPage />
    </TestMemoryRouter>
  );
}

describe("HealthPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the live backend health status", async () => {
    mockedUseLoaderData.mockReturnValue({
      health: Promise.resolve({
        service: "trip-planner-api",
        status: "ok",
        environment: "local",
        version: "0.1.0",
      }),
    });

    renderHealthPage();

    expect(screen.getByText("Checking backend health")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "trip-planner-api" })).toBeInTheDocument();
    });

    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.getByText("local")).toBeInTheDocument();
    expect(screen.getByText("0.1.0")).toBeInTheDocument();
  });

  it("says the backend is degraded and why, when its database is not ready (issue 1851)", async () => {
    mockedUseLoaderData.mockReturnValue({
      health: Promise.resolve({
        service: "trip-planner-api",
        status: "degraded",
        environment: "production",
        version: "0.1.0",
        database: {
          ready: false,
          reason: "OperationalError: database initialisation failed",
          checked_at: "2026-09-22T15:00:00+00:00",
        },
      }),
    });

    renderHealthPage();

    await waitFor(() => {
      expect(screen.getByTestId("health-state")).toHaveTextContent("degraded");
    });
    expect(screen.getByTestId("health-database")).toHaveTextContent(
      "Not ready: OperationalError: database initialisation failed"
    );
    expect(screen.getByTestId("health-database")).toHaveTextContent("Trips cannot be saved or loaded");
  });

  it("renders route-level loading and error treatment through the shared client seam", async () => {
    let rejectRequest: ((reason?: unknown) => void) | undefined;
    mockedUseLoaderData.mockReturnValue({
      health: new Promise((_, reject) => {
        rejectRequest = reject;
      }),
    });

    renderHealthPage();

    expect(screen.getByText("Checking backend health")).toBeInTheDocument();

    rejectRequest?.(new Error("Backend offline"));

    await waitFor(() => {
      expect(screen.getByText("Backend health check failed")).toBeInTheDocument();
    });

    expect(screen.getByText("Backend offline")).toBeInTheDocument();
  });
});
