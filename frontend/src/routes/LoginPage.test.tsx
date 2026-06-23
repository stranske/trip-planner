import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { login } from "../api/auth";
import { LoginPage } from "./LoginPage";
import { TestMemoryRouter } from "../test/router";

vi.mock("../api/auth", () => ({
  login: vi.fn(),
}));

const mockedLogin = vi.mocked(login);
const mockedNavigate = vi.fn();
const mockedRevalidate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
    useRevalidator: () => ({ revalidate: mockedRevalidate }),
    useSearchParams: () => [new URLSearchParams("next=%2Ftrips"), vi.fn()],
  };
});

describe("LoginPage", () => {
  afterEach(() => {
    cleanup();
    mockedLogin.mockReset();
    mockedNavigate.mockReset();
    mockedRevalidate.mockReset();
  });

  it("submits credentials and navigates to the requested protected route", async () => {
    mockedLogin.mockResolvedValue({
      user: {
        user_id: "user:test",
        email: "traveler@example.com",
        display_name: "Traveler",
      },
    });

    render(
      <TestMemoryRouter>
        <LoginPage />
      </TestMemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "traveler@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(mockedLogin).toHaveBeenCalledWith({
        email: "traveler@example.com",
        password: "password123",
      });
    });
    expect(mockedRevalidate).toHaveBeenCalled();
    expect(mockedNavigate).toHaveBeenCalledWith("/trips");
  });

  it("renders API errors inline", async () => {
    mockedLogin.mockRejectedValue(new Error("Email or password was not recognized."));

    render(
      <TestMemoryRouter>
        <LoginPage />
      </TestMemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "traveler@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrongpass" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Email or password was not recognized.");
    });
  });
});
