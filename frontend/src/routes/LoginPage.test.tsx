import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { login } from "../api/auth";
import { LoginPage } from "./LoginPage";

vi.mock("../api/auth", () => ({
  login: vi.fn(),
}));

const mockedLogin = vi.mocked(login);
const mockedNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
    useSearchParams: () => [new URLSearchParams("next=%2Fworkspace%2Ftrip-leisure-kyoto-draft"), vi.fn()],
  };
});

describe("LoginPage", () => {
  afterEach(() => {
    cleanup();
    mockedLogin.mockReset();
    mockedNavigate.mockReset();
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
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
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
    expect(mockedNavigate).toHaveBeenCalledWith("/workspace/trip-leisure-kyoto-draft");
  });

  it("renders API errors inline", async () => {
    mockedLogin.mockRejectedValue(new Error("Email or password was not recognized."));

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "traveler@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrongpass" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Email or password was not recognized.");
    });
  });
});
