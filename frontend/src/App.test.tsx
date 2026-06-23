import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { login, logout, signup } from "./api/auth";
import App from "./App";
import { LoginPage } from "./routes/LoginPage";
import { SignupPage } from "./routes/SignupPage";
import type { RootLoaderData } from "./router";

vi.mock("./api/auth", () => ({
  login: vi.fn(),
  logout: vi.fn(),
  signup: vi.fn(),
}));

const mockedLogin = vi.mocked(login);
const mockedLogout = vi.mocked(logout);
const mockedSignup = vi.mocked(signup);

const signedInSession: NonNullable<RootLoaderData["session"]> = {
  user: {
    user_id: "user:test",
    email: "traveler@example.com",
    display_name: "Traveler",
  },
};

function renderAppWithSession(
  initialSession: RootLoaderData["session"],
  initialEntries = ["/login"]
) {
  let currentSession = initialSession;
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: <App />,
        loader: () => ({ session: currentSession }),
        children: [
          {
            path: "login",
            element: <LoginPage />,
          },
          {
            path: "signup",
            element: <SignupPage />,
          },
          {
            path: "trips",
            element: <section>Saved trips</section>,
          },
        ],
      },
    ],
    { initialEntries }
  );

  return {
    router,
    setSession: (session: RootLoaderData["session"]) => {
      currentSession = session;
    },
    ...render(<RouterProvider router={router} />),
  };
}

describe("App auth header", () => {
  afterEach(() => {
    cleanup();
    mockedLogin.mockReset();
    mockedLogout.mockReset();
    mockedSignup.mockReset();
  });

  it("refreshes the root header after login without a full reload", async () => {
    const app = renderAppWithSession(null);
    mockedLogin.mockImplementation(async () => {
      app.setSession(signedInSession);
      return signedInSession;
    });

    expect(await screen.findByText(/Sign in to continue planning trips/)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Login" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "traveler@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByText(/Signed in as Traveler/)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Trips" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Login" })).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Signup" })).not.toBeInTheDocument();
    });
    expect(app.router.state.location.pathname).toBe("/trips");
  });

  it("refreshes the root header after signup without a full reload", async () => {
    const app = renderAppWithSession(null, ["/signup"]);
    mockedSignup.mockImplementation(async () => {
      app.setSession(signedInSession);
      return signedInSession;
    });

    expect(await screen.findByText(/Sign in to continue planning trips/)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Signup" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Display name"), {
      target: { value: "Traveler" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "traveler@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(screen.getByText(/Signed in as Traveler/)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Trips" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Login" })).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Signup" })).not.toBeInTheDocument();
    });
    expect(app.router.state.location.pathname).toBe("/trips");
  });

  it("refreshes the root header after logout without a full reload", async () => {
    const app = renderAppWithSession(signedInSession, ["/trips"]);
    mockedLogout.mockImplementation(async () => {
      app.setSession(null);
      return { signed_out: true };
    });

    expect(await screen.findByText(/Signed in as Traveler/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => {
      expect(screen.getByText(/Sign in to continue planning trips/)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Login" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Signup" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
    });
    expect(app.router.state.location.pathname).toBe("/login");
  });
});
