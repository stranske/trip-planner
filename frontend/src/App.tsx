import { startTransition, useState } from "react";
import {
  NavLink,
  Outlet,
  useLoaderData,
  useNavigate,
  useRevalidator,
  useRouteError,
} from "react-router-dom";

import { logout } from "./api/auth";
import { getErrorMessage } from "./lib/api/errors";
import type { RootLoaderData } from "./router";

export function InitialRouteFallback() {
  return (
    <div className="app-shell">
      <section className="status-card">
        <p className="status-label">Backend status</p>
        <h2>Waking up the server</h2>
        <p>Checking /api/health before loading the planner.</p>
      </section>
    </div>
  );
}

export function RootErrorBoundary() {
  const error = useRouteError();

  return (
    <div className="app-shell">
      <section className="status-card status-card-error">
        <p className="status-label">Backend status</p>
        <h2>Backend startup check failed</h2>
        <p>
          {getErrorMessage(
            error,
            "The backend did not respond before the cold-start retry budget was exhausted."
          )}
        </p>
      </section>
    </div>
  );
}

export default function App() {
  const { session } = useLoaderData() as RootLoaderData;
  const navigate = useNavigate();
  const revalidator = useRevalidator();
  const [isSigningOut, setIsSigningOut] = useState(false);

  async function handleSignOut() {
    setIsSigningOut(true);
    try {
      await logout();
      startTransition(() => {
        revalidator.revalidate();
        navigate("/login");
      });
    } finally {
      setIsSigningOut(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Trip Planner</p>
          <h1>Plan trips with a saved workspace</h1>
          <p className="lede">
            {session
              ? `Signed in as ${session.user.display_name}. Open a trip to keep decisions, notes, budgets, and route options together.`
              : "Sign in to continue planning trips, compare routes, and keep notes in one place."}
          </p>
        </div>
        <nav aria-label="Primary">
          <NavLink to="/health">Status</NavLink>
          {session ? (
            <>
              <NavLink to="/trips">Trips</NavLink>
              <NavLink to="/trips/new">New Trip</NavLink>
              <button type="button" className="nav-button" onClick={handleSignOut} disabled={isSigningOut}>
                {isSigningOut ? "Signing out..." : "Sign out"}
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login">Login</NavLink>
              <NavLink to="/signup">Signup</NavLink>
            </>
          )}
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
