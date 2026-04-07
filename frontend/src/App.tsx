import { NavLink, Outlet } from "react-router-dom";

const DEFAULT_WORKSPACE_TRIP = "trip-leisure-kyoto-draft";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Trip Planner Runtime</p>
          <h1>Persisted planner workspace</h1>
          <p className="lede">
            The React shell now consumes persisted trip, session, and scenario state from the live
            FastAPI runtime.
          </p>
        </div>
        <nav aria-label="Primary">
          <NavLink to="/" end>
            Health
          </NavLink>
          <NavLink to={`/workspace/${DEFAULT_WORKSPACE_TRIP}`}>Workspace</NavLink>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
