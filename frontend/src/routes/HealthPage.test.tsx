import { render, screen, waitFor } from "@testing-library/react";
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
