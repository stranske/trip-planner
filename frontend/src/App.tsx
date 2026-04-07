import { NavLink, Route, Routes } from "react-router-dom";

import { HealthPage } from "./routes/HealthPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Trip Planner Runtime</p>
          <h1>First runnable full-stack slice</h1>
          <p className="lede">
            The React shell is now wired to a live FastAPI backend instead of static-only planner
            mocks.
          </p>
        </div>
        <nav aria-label="Primary">
          <NavLink to="/" end>
            Health
          </NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<HealthPage />} />
        </Routes>
      </main>
    </div>
  );
}
