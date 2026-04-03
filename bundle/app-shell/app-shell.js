/**
 * Frontend application-shell foundation for issue #556.
 *
 * @import {
 *   AppRouteId,
 *   FrontendAppRouteRecord,
 *   FrontendShellState,
 *   FrontendTripSummaryRecord,
 *   FrontendWorkspaceRecord,
 *   WorkspaceStatus,
 * } from "./contracts"
 */

const APP_ROUTES = /** @type {const} */ ([
  {
    route_id: "dashboard",
    label: "Dashboard",
    path: "/app",
    description: "Saved trips, launch points, and account-level planning signals.",
    requires_active_trip: false,
    modes: ["leisure", "business"],
  },
  {
    route_id: "trip_workspace",
    label: "Trip Workspace",
    path: "/app/trip",
    description: "Trip summary, scenario staging, and saved-workspace context.",
    requires_active_trip: true,
    modes: ["leisure", "business"],
  },
  {
    route_id: "planner_workspace",
    label: "Planner",
    path: "/app/trip/planner",
    description: "Interactive planning checkpoints and next-step actions.",
    requires_active_trip: true,
    modes: ["leisure", "business"],
  },
  {
    route_id: "approval_center",
    label: "Approval Readiness",
    path: "/app/trip/approval",
    description: "Business-trip policy posture, comparables, and approval packet progress.",
    requires_active_trip: true,
    modes: ["business"],
  },
]);

const HTML_ESCAPE_LOOKUP = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

/**
 * @param {unknown} value
 * @returns {string}
 */
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => HTML_ESCAPE_LOOKUP[character]);
}

/**
 * @param {unknown} value
 * @returns {string}
 */
function escapeAttribute(value) {
  return escapeHtml(value);
}

/**
 * @param {FrontendShellState["session"]} session
 * @param {FrontendTripSummaryRecord[]} trips
 * @param {string | null} activeTripId
 * @returns {FrontendTripSummaryRecord | null}
 */
function resolveActiveTrip(session, trips, activeTripId) {
  if (activeTripId) {
    return trips.find((trip) => trip.trip_id === activeTripId) ?? null;
  }

  return (
    trips.find((trip) => trip.mode === session.default_trip_mode) ??
    trips[0] ??
    null
  );
}

/**
 * @param {FrontendTripSummaryRecord | null} activeTrip
 * @param {FrontendWorkspaceRecord} workspace
 * @returns {FrontendAppRouteRecord[]}
 */
export function getShellRoutes(activeTrip, workspace) {
  return APP_ROUTES.filter((route) => {
    if (route.requires_active_trip && !activeTrip) {
      return false;
    }

    if (route.route_id === "approval_center") {
      return Boolean(
        activeTrip?.mode === "business" || workspace.planner_panel_state?.policy_evaluation
      );
    }

    return !activeTrip || route.modes.includes(activeTrip.mode);
  });
}

/**
 * @param {FrontendTripSummaryRecord | null} activeTrip
 * @param {FrontendWorkspaceRecord} workspace
 * @returns {AppRouteId}
 */
function getDefaultRoute(activeTrip, workspace) {
  if (!activeTrip) {
    return "dashboard";
  }

  if (activeTrip.mode === "business" && workspace.planner_panel_state?.policy_evaluation) {
    return "approval_center";
  }

  return "trip_workspace";
}

/**
 * @param {{
 *   session: FrontendShellState["session"];
 *   trips?: FrontendTripSummaryRecord[];
 *   active_trip_id?: string | null;
 *   active_route?: AppRouteId;
 *   workspace?: Partial<FrontendWorkspaceRecord>;
 * }} input
 * @returns {FrontendShellState}
 */
export function buildAppShellState(input) {
  const trips = input.trips ?? [];
  const activeTrip = resolveActiveTrip(input.session, trips, input.active_trip_id ?? null);
  const workspace = {
    trip_id: input.workspace?.trip_id ?? activeTrip?.trip_id ?? null,
    status:
      input.workspace?.status ??
      (activeTrip ? "ready" : "empty"),
    planner_panel_state: input.workspace?.planner_panel_state ?? null,
    loading_message: input.workspace?.loading_message ?? null,
    error_message: input.workspace?.error_message ?? null,
    persistence_summary: input.workspace?.persistence_summary ?? [],
  };
  const routes = getShellRoutes(activeTrip, workspace);
  const defaultRoute = getDefaultRoute(activeTrip, workspace);
  const activeRoute =
    routes.find((route) => route.route_id === input.active_route)?.route_id ?? defaultRoute;

  return {
    session: input.session,
    routes,
    active_route: activeRoute,
    trips,
    active_trip_id: activeTrip?.trip_id ?? null,
    workspace,
  };
}

/**
 * @param {FrontendShellState} initialState
 */
export function createAppShellStore(initialState) {
  /** @type {FrontendShellState} */
  let state = buildAppShellState(initialState);
  const listeners = new Set();

  const notify = () => {
    listeners.forEach((listener) => listener(state));
  };

  return {
    getState() {
      return state;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    setRoute(routeId) {
      state = buildAppShellState({ ...state, active_route: routeId });
      notify();
    },
    setActiveTrip(tripId) {
      const isTripChange = state.active_trip_id !== tripId;
      state = buildAppShellState({
        ...state,
        active_trip_id: tripId,
        workspace: isTripChange
          ? {
              trip_id: tripId,
              status: "empty",
              planner_panel_state: null,
              loading_message: null,
              error_message: null,
              persistence_summary: state.workspace.persistence_summary,
            }
          : {
              ...state.workspace,
              trip_id: tripId,
            },
      });
      notify();
    },
    setWorkspaceStatus(status, message = null) {
      state = buildAppShellState({
        ...state,
        workspace: {
          ...state.workspace,
          status,
          loading_message: status === "loading" ? message : null,
          error_message: status === "error" ? message : null,
        },
      });
      notify();
    },
  };
}

/**
 * @param {WorkspaceStatus} status
 * @returns {string}
 */
function formatStatusLabel(status) {
  if (status === "loading") {
    return "Loading";
  }

  if (status === "error") {
    return "Needs attention";
  }

  if (status === "empty") {
    return "Waiting for trip context";
  }

  return "Ready";
}

/**
 * @param {FrontendTripSummaryRecord} trip
 * @returns {string}
 */
function renderTripSummaryCard(trip) {
  return `
    <button type="button" class="shell-trip-card" data-shell-trip="${escapeAttribute(trip.trip_id)}">
      <div class="shell-trip-card-header">
        <strong>${escapeHtml(trip.title)}</strong>
        <span class="shell-mode-pill shell-mode-pill--${escapeAttribute(trip.mode)}">${escapeHtml(trip.mode)}</span>
      </div>
      <p>${escapeHtml(trip.summary)}</p>
      <div class="shell-chip-row">
        <span class="shell-chip">${escapeHtml(trip.status)}</span>
        <span class="shell-chip">${escapeHtml(trip.primary_regions.join(" · "))}</span>
        <span class="shell-chip">${escapeHtml(`${trip.scenario_count} scenarios`)}</span>
        <span class="shell-chip">${escapeHtml(`${trip.pending_checkpoint_count} checkpoints`)}</span>
      </div>
    </button>
  `;
}

/**
 * @param {FrontendShellState} state
 * @returns {string}
 */
function renderRouteTabs(state) {
  return `
    <nav class="shell-route-tabs" aria-label="Application shell routes">
      ${state.routes
        .map(
          (route) => `
            <button
              type="button"
              class="shell-route-tab${route.route_id === state.active_route ? " is-active" : ""}"
              data-shell-route="${escapeAttribute(route.route_id)}"
              aria-pressed="${route.route_id === state.active_route}"
            >
              <span>${escapeHtml(route.label)}</span>
              <small>${escapeHtml(route.description)}</small>
            </button>
          `
        )
        .join("")}
    </nav>
  `;
}

/**
 * @param {FrontendWorkspaceRecord} workspace
 * @returns {string}
 */
export function renderWorkspaceStatusBoundary(workspace) {
  if (workspace.status === "ready") {
    return "";
  }

  const message =
    workspace.loading_message ??
    workspace.error_message ??
    "Select a trip to start the workspace shell.";

  return `
    <section class="shell-status shell-status--${escapeAttribute(workspace.status)}" aria-label="Workspace status">
      <strong>${escapeHtml(formatStatusLabel(workspace.status))}</strong>
      <p>${escapeHtml(message)}</p>
    </section>
  `;
}

/**
 * @param {FrontendShellState} state
 * @returns {string}
 */
function renderDashboardView(state) {
  return `
    <section class="shell-view shell-view--dashboard">
      <div class="shell-hero">
        <div>
          <p class="shell-eyebrow">Signed-in planning home</p>
          <h2>${escapeHtml(state.session.display_name)}</h2>
          <p>${escapeHtml(state.session.organization ?? "Independent traveler")} can resume saved trips or launch a new flow once issue #557 adds entry screens.</p>
        </div>
        <div class="shell-chip-row">
          <span class="shell-chip">${escapeHtml(`${state.trips.length} saved trips`)}</span>
          <span class="shell-chip">${escapeHtml(`default ${state.session.default_trip_mode} mode`)}</span>
        </div>
      </div>
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Saved trips</h3>
          <span class="shell-meta">mode-aware shell entry points</span>
        </div>
        <div class="shell-trip-grid">
          ${state.trips.map((trip) => renderTripSummaryCard(trip)).join("")}
        </div>
      </section>
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>State integration seams</h3>
          <span class="shell-meta">what later issues should plug into</span>
        </div>
        <ul class="shell-list">
          ${state.workspace.persistence_summary.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </section>
    </section>
  `;
}

/**
 * @param {FrontendShellState} state
 * @returns {string}
 */
function renderTripWorkspaceView(state) {
  const activeTrip = state.trips.find((trip) => trip.trip_id === state.active_trip_id) ?? null;
  const boundary = renderWorkspaceStatusBoundary(state.workspace);
  if (!activeTrip) {
    return boundary;
  }

  const plannerState = state.workspace.planner_panel_state;
  const scenarioSummary = plannerState
    ? `${plannerState.outputs.length} outputs, ${plannerState.pending_decisions.length} decision checkpoint, ${plannerState.option_set.options.length} surfaced options`
    : "Planner payload not mounted yet.";

  return `
    <section class="shell-view shell-view--workspace">
      ${boundary}
      <div class="shell-hero">
        <div>
          <p class="shell-eyebrow">${escapeHtml(`${activeTrip.mode} workspace`)}</p>
          <h2>${escapeHtml(activeTrip.title)}</h2>
          <p>${escapeHtml(activeTrip.summary)}</p>
        </div>
        <div class="shell-chip-row">
          <span class="shell-chip">${escapeHtml(`${activeTrip.start_date ?? "TBD"} to ${activeTrip.end_date ?? "TBD"}`)}</span>
          <span class="shell-chip">${escapeHtml(activeTrip.primary_regions.join(" · "))}</span>
          <span class="shell-chip">${escapeHtml(`${activeTrip.scenario_count} scenarios`)}</span>
        </div>
      </div>
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Workspace shell contract</h3>
          <span class="shell-meta">${escapeHtml(formatStatusLabel(state.workspace.status))}</span>
        </div>
        <p>${escapeHtml(scenarioSummary)}</p>
        <ul class="shell-list">
          ${state.workspace.persistence_summary.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </section>
    </section>
  `;
}

/**
 * @param {FrontendShellState} state
 * @returns {string}
 */
function renderPlannerWorkspaceView(state) {
  const boundary = renderWorkspaceStatusBoundary(state.workspace);
  const plannerState = state.workspace.planner_panel_state;
  if (!plannerState) {
    return `${boundary}<p class="shell-empty-state">Planner route will hydrate once orchestration state is available.</p>`;
  }

  return `
    <section class="shell-view shell-view--planner">
      ${boundary}
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Planner route</h3>
          <span class="shell-meta">${escapeHtml(plannerState.planner_behavior.trip_stage)}</span>
        </div>
        <p>${escapeHtml(plannerState.trip.summary)}</p>
        <div class="shell-chip-row">
          <span class="shell-chip">${escapeHtml(`${plannerState.outputs.length} outputs`)}</span>
          <span class="shell-chip">${escapeHtml(`${plannerState.pending_decisions.length} pending decisions`)}</span>
          <span class="shell-chip">${escapeHtml(`${plannerState.option_set.options.length} options`)}</span>
        </div>
      </section>
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Immediate actions</h3>
          <span class="shell-meta">carried from canonical planner state</span>
        </div>
        <ul class="shell-list">
          ${plannerState.next_step_actions
            .map(
              (action) =>
                `<li><strong>${escapeHtml(action.label)}:</strong> ${escapeHtml(action.description)}</li>`
            )
            .join("")}
        </ul>
      </section>
    </section>
  `;
}

/**
 * @param {FrontendShellState} state
 * @returns {string}
 */
function renderApprovalCenterView(state) {
  const boundary = renderWorkspaceStatusBoundary(state.workspace);
  const policy = state.workspace.planner_panel_state?.policy_evaluation;
  const proposal = state.workspace.planner_panel_state?.proposal;

  if (!policy || !proposal) {
    return `${boundary}<p class="shell-empty-state">Approval readiness activates only for business trips with policy evaluation output.</p>`;
  }

  return `
    <section class="shell-view shell-view--approval">
      ${boundary}
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Approval posture</h3>
          <span class="shell-meta">${escapeHtml(policy.status)}</span>
        </div>
        <p>${escapeHtml(state.workspace.planner_panel_state.trip.summary)}</p>
        <div class="shell-chip-row">
          <span class="shell-chip">${escapeHtml(`${policy.approval_requirements.length} approvers`)}</span>
          <span class="shell-chip">${escapeHtml(`${proposal.comparables.length} comparables`)}</span>
          <span class="shell-chip">${escapeHtml(`${proposal.justifications?.length ?? 0} justifications`)}</span>
        </div>
      </section>
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Approval packet seams</h3>
          <span class="shell-meta">proposal + policy evaluation</span>
        </div>
        <ul class="shell-list">
          ${policy.approval_requirements
            .map(
              (requirement) =>
                `<li>${escapeHtml(requirement.role)}: ${escapeHtml(requirement.reason)}</li>`
            )
            .join("")}
        </ul>
      </section>
    </section>
  `;
}

/**
 * @param {FrontendShellState} state
 * @returns {string}
 */
function renderActiveView(state) {
  if (state.active_route === "trip_workspace") {
    return renderTripWorkspaceView(state);
  }

  if (state.active_route === "planner_workspace") {
    return renderPlannerWorkspaceView(state);
  }

  if (state.active_route === "approval_center") {
    return renderApprovalCenterView(state);
  }

  return renderDashboardView(state);
}

/**
 * @param {FrontendShellState} state
 * @returns {string}
 */
export function renderAppShellLayout(state) {
  const activeTrip = state.trips.find((trip) => trip.trip_id === state.active_trip_id) ?? null;

  return `
    <section class="planner-app-shell" data-shell-route="${escapeAttribute(state.active_route)}">
      <header class="shell-header">
        <div>
          <p class="shell-eyebrow">Trip planner application shell</p>
          <h1>Mode-aware travel planning foundation</h1>
          <p>${escapeHtml(activeTrip ? `Active trip: ${activeTrip.title}` : "Choose a trip context to enter the workspace shell.")}</p>
        </div>
        <div class="shell-account-summary">
          <strong>${escapeHtml(state.session.display_name)}</strong>
          <span>${escapeHtml(state.session.organization ?? "Independent traveler")}</span>
        </div>
      </header>
      ${renderRouteTabs(state)}
      <main class="shell-main">
        ${renderActiveView(state)}
      </main>
    </section>
  `;
}

/**
 * @param {HTMLElement & { innerHTML: string }} mountNode
 * @param {FrontendShellState} initialState
 */
export function renderAppShell(mountNode, initialState) {
  const store = createAppShellStore(initialState);

  const rerender = () => {
    mountNode.innerHTML = renderAppShellLayout(store.getState());
  };

  const handleClick = (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }

    const routeTarget = event.target.closest("[data-shell-route]");
    if (routeTarget?.dataset.shellRoute) {
      store.setRoute(routeTarget.dataset.shellRoute);
      mountNode.dispatchEvent(
        new CustomEvent("shell:route-change", {
          detail: store.getState().active_route,
        })
      );
      return;
    }

    const tripTarget = event.target.closest("[data-shell-trip]");
    if (tripTarget?.dataset.shellTrip) {
      store.setActiveTrip(tripTarget.dataset.shellTrip);
      mountNode.dispatchEvent(
        new CustomEvent("shell:trip-change", {
          detail: store.getState().active_trip_id,
        })
      );
    }
  };

  const unsubscribe = store.subscribe(rerender);
  mountNode.addEventListener("click", handleClick);
  rerender();

  return {
    getState: store.getState,
    setRoute(routeId) {
      store.setRoute(routeId);
    },
    setActiveTrip(tripId) {
      store.setActiveTrip(tripId);
    },
    destroy() {
      unsubscribe();
      mountNode.removeEventListener("click", handleClick);
    },
  };
}
