import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { signup } from "../api/auth";
import { SignupPage } from "./SignupPage";
import { TestMemoryRouter } from "../test/router";

vi.mock("../api/auth", () => ({
  signup: vi.fn(),
}));

const mockedSignup = vi.mocked(signup);
const mockedNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
  };
});

describe("SignupPage", () => {
  afterEach(() => {
    cleanup();
    mockedSignup.mockReset();
    mockedNavigate.mockReset();
  });

  it("creates an account and routes into the protected trip list", async () => {
    mockedSignup.mockResolvedValue({
      user: {
        user_id: "user:test",
        email: "owner@example.com",
        display_name: "Owner",
      },
    });

    render(
      <TestMemoryRouter>
        <SignupPage />
      </TestMemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Owner" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "owner@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(mockedSignup).toHaveBeenCalledWith({
        display_name: "Owner",
        email: "owner@example.com",
        password: "password123",
      });
    });
    expect(mockedNavigate).toHaveBeenCalledWith("/trips");
  });
});
