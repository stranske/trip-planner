import { startTransition, useState } from "react";
import { NavLink, Outlet, useLoaderData, useNavigate } from "react-router-dom";

import { logout } from "./api/auth";
import type { RootLoaderData } from "./router";

export default function App() {
  const { session } = useLoaderData() as RootLoaderData;
  const navigate = useNavigate();
  const [isSigningOut, setIsSigningOut] = useState(false);

  async function handleSignOut() {
    setIsSigningOut(true);
    try {
      await logout();
      startTransition(() => {
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
