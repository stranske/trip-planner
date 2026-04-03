/**
 * Frontend application-shell foundation for issue #556.
 *
 * @import {
 *   AppRouteId,
  *   FrontendAppRouteRecord,
 *   FrontendAccountEntryRecord,
 *   FrontendLaunchFlowRecord,
 *   FrontendRecentSessionRecord,
 *   FrontendShellState,
 *   FrontendTripSummaryRecord,
 *   LaunchFlowId,
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
 * @param {FrontendAccountEntryRecord | Partial<FrontendAccountEntryRecord> | undefined} accountEntry
 * @returns {FrontendAccountEntryRecord}
 */
function normalizeAccountEntry(session, accountEntry) {
  const launchFlows = accountEntry?.launch_flows ?? [];
  const selectedLaunchId = launchFlows.some(
    (flow) => flow.launch_id === accountEntry?.selected_launch_id
  )
    ? accountEntry?.selected_launch_id
    : launchFlows.find((flow) => flow.mode === session.default_trip_mode)?.launch_id ??
      launchFlows[0]?.launch_id ??
      null;

  return {
    traveler_profiles: accountEntry?.traveler_profiles ?? [],
    recent_sessions: accountEntry?.recent_sessions ?? [],
    launch_flows: launchFlows,
    selected_launch_id: selectedLaunchId,
    empty_state_message: accountEntry?.empty_state_message ?? null,
  };
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
 *   account_entry?: Partial<FrontendAccountEntryRecord>;
 *   workspace?: Partial<FrontendWorkspaceRecord>;
 * }} input
 * @returns {FrontendShellState}
 */
export function buildAppShellState(input) {
  const trips = input.trips ?? [];
  const activeTrip = resolveActiveTrip(input.session, trips, input.active_trip_id ?? null);
  const accountEntry = normalizeAccountEntry(input.session, input.account_entry);
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
    account_entry: accountEntry,
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
    setEntryLaunch(launchId) {
      if (!state.account_entry.launch_flows.some((flow) => flow.launch_id === launchId)) {
        return;
      }

      state = buildAppShellState({
        ...state,
        active_route: "dashboard",
        account_entry: {
          ...state.account_entry,
          selected_launch_id: launchId,
        },
        workspace: {
          ...state.workspace,
          status: "empty",
          loading_message: null,
          error_message: null,
        },
      });
      notify();
    },
    resumeSession(sessionId) {
      const session = state.account_entry.recent_sessions.find(
        (candidate) => candidate.session_id === sessionId
      );

      if (!session?.trip_id) {
        state = buildAppShellState({
          ...state,
          active_route: "dashboard",
          workspace: {
            ...state.workspace,
            status: "error",
            loading_message: null,
            error_message: "Selected session is no longer available.",
          },
        });
        notify();
        return;
      }

      state = buildAppShellState({
        ...state,
        active_trip_id: session.trip_id,
        active_route: session.resume_route,
        account_entry: {
          ...state.account_entry,
          selected_launch_id: "resume_existing_trip",
        },
        workspace: {
          ...state.workspace,
          trip_id: session.trip_id,
          status: "empty",
          planner_panel_state: null,
          loading_message: "Rehydrating the saved session entry point.",
          error_message: null,
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
 * @param {FrontendRecentSessionRecord} session
 * @returns {string}
 */
function renderRecentSessionCard(session) {
  return `
    <button type="button" class="shell-trip-card shell-trip-card--session" data-shell-session="${escapeAttribute(session.session_id)}">
      <div class="shell-trip-card-header">
        <strong>${escapeHtml(session.label)}</strong>
        <span class="shell-mode-pill shell-mode-pill--${escapeAttribute(session.mode)}">${escapeHtml(session.mode)}</span>
      </div>
      <p>${escapeHtml(session.summary)}</p>
      <div class="shell-chip-row">
        <span class="shell-chip">${escapeHtml(session.last_active_label)}</span>
        <span class="shell-chip">${escapeHtml(`resume ${session.resume_route}`)}</span>
      </div>
    </button>
  `;
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
 * @param {FrontendLaunchFlowRecord} flow
 * @param {boolean} isSelected
 * @returns {string}
 */
function renderLaunchFlowCard(flow, isSelected) {
  return `
    <button
      type="button"
      class="shell-trip-card shell-trip-card--launch${isSelected ? " is-active" : ""}"
      data-shell-launch="${escapeAttribute(flow.launch_id)}"
    >
      <div class="shell-trip-card-header">
        <strong>${escapeHtml(flow.title)}</strong>
        <span class="shell-mode-pill shell-mode-pill--${escapeAttribute(flow.mode)}">${escapeHtml(flow.mode)}</span>
      </div>
      <p>${escapeHtml(flow.summary)}</p>
      <div class="shell-chip-row">
        <span class="shell-chip">${escapeHtml(flow.cta_label)}</span>
        <span class="shell-chip">${escapeHtml(`${flow.starting_needs.length} startup cues`)}</span>
      </div>
    </button>
  `;
}

/**
 * @param {FrontendShellState["account_entry"]["traveler_profiles"][number]} profile
 * @returns {string}
 */
function renderTravelerProfileCard(profile) {
  return `
    <article class="shell-panel shell-panel--profile">
      <div class="shell-panel-header">
        <h3>${escapeHtml(profile.label)}</h3>
        <span class="shell-meta">${escapeHtml(profile.mode)}</span>
      </div>
      <p>${escapeHtml(profile.summary)}</p>
      <p class="shell-meta">${escapeHtml(profile.readiness)}</p>
    </article>
  `;
}

/**
 * @param {FrontendShellState} state
 * @returns {FrontendLaunchFlowRecord | null}
 */
function getSelectedLaunchFlow(state) {
  return (
    state.account_entry.launch_flows.find(
      (flow) => flow.launch_id === state.account_entry.selected_launch_id
    ) ?? null
  );
}

/**
 * @param {FrontendShellState} state
 * @returns {string}
 */
function renderSelectedLaunchFlow(state) {
  const flow = getSelectedLaunchFlow(state);
  if (!flow) {
    return `
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Launch detail</h3>
          <span class="shell-meta">no launch selected</span>
        </div>
        <p>Select a launch option to see the startup data the entry layer must persist.</p>
      </section>
    `;
  }

  const linkedSession = flow.recent_session_id
    ? state.account_entry.recent_sessions.find(
        (session) => session.session_id === flow.recent_session_id
      )
    : null;
  const linkedTrip = flow.trip_id
    ? state.trips.find((trip) => trip.trip_id === flow.trip_id) ?? null
    : null;

  return `
    <section class="shell-panel">
      <div class="shell-panel-header">
        <h3>${escapeHtml(flow.title)}</h3>
        <span class="shell-meta">${escapeHtml(flow.cta_label)}</span>
      </div>
      <p>${escapeHtml(flow.summary)}</p>
      <ul class="shell-list">
        ${flow.starting_needs.map((need) => `<li>${escapeHtml(need)}</li>`).join("")}
      </ul>
      <div class="shell-chip-row">
        ${
          flow.profile_id
            ? `<span class="shell-chip">${escapeHtml(`profile ${flow.profile_id}`)}</span>`
            : ""
        }
        ${
          linkedSession
            ? `<span class="shell-chip">${escapeHtml(`session ${linkedSession.label}`)}</span>`
            : ""
        }
        ${
          linkedTrip
            ? `<span class="shell-chip">${escapeHtml(`trip ${linkedTrip.title}`)}</span>`
            : ""
        }
      </div>
      ${
        flow.policy_context
          ? `<p class="shell-meta">${escapeHtml(flow.policy_context)}</p>`
          : ""
      }
    </section>
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
  const hasRecentSessions = state.account_entry.recent_sessions.length > 0;
  const hasSavedTrips = state.trips.length > 0;

  return `
    <section class="shell-view shell-view--dashboard">
      <div class="shell-hero">
        <div>
          <p class="shell-eyebrow">Signed-in planning home</p>
          <h2>${escapeHtml(state.session.display_name)}</h2>
          <p>${escapeHtml(state.session.organization ?? "Independent traveler")} can enter saved planning work, launch a new leisure or business trip, and keep mode-specific startup needs visible from the first screen.</p>
        </div>
        <div class="shell-chip-row">
          <span class="shell-chip">${escapeHtml(`${state.trips.length} saved trips`)}</span>
          <span class="shell-chip">${escapeHtml(`${state.account_entry.recent_sessions.length} recent sessions`)}</span>
          <span class="shell-chip">${escapeHtml(`default ${state.session.default_trip_mode} mode`)}</span>
        </div>
      </div>
      ${
        state.account_entry.empty_state_message
          ? `
            <section class="shell-status shell-status--empty" aria-label="Entry empty state">
              <strong>Trip entry is ready for first use</strong>
              <p>${escapeHtml(state.account_entry.empty_state_message)}</p>
            </section>
          `
          : ""
      }
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Recent sessions</h3>
          <span class="shell-meta">resume the last planner or approval checkpoint</span>
        </div>
        ${
          hasRecentSessions
            ? `
              <div class="shell-trip-grid">
                ${state.account_entry.recent_sessions.map((session) => renderRecentSessionCard(session)).join("")}
              </div>
            `
            : "<p class=\"shell-empty-state\">No resumable sessions yet. The next trip launch will create the first one.</p>"
        }
      </section>
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Trip launch flows</h3>
          <span class="shell-meta">new leisure, new business, and resume entry paths</span>
        </div>
        <div class="shell-trip-grid">
          ${state.account_entry.launch_flows
            .map((flow) => renderLaunchFlowCard(flow, flow.launch_id === state.account_entry.selected_launch_id))
            .join("")}
        </div>
      </section>
      ${renderSelectedLaunchFlow(state)}
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Traveler profile context</h3>
          <span class="shell-meta">what account-entry should carry into launch</span>
        </div>
        <div class="shell-trip-grid">
          ${state.account_entry.traveler_profiles.map((profile) => renderTravelerProfileCard(profile)).join("")}
        </div>
      </section>
      <section class="shell-panel">
        <div class="shell-panel-header">
          <h3>Saved trips</h3>
          <span class="shell-meta">mode-aware shell entry points</span>
        </div>
        ${
          hasSavedTrips
            ? `
              <div class="shell-trip-grid">
                ${state.trips.map((trip) => renderTripSummaryCard(trip)).join("")}
              </div>
            `
            : "<p class=\"shell-empty-state\">No saved trips yet. Launching a new trip should seed the first persisted trip summary.</p>"
        }
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
      return;
    }

    const launchTarget = event.target.closest("[data-shell-launch]");
    if (launchTarget?.dataset.shellLaunch) {
      store.setEntryLaunch(launchTarget.dataset.shellLaunch);
      mountNode.dispatchEvent(
        new CustomEvent("shell:launch-change", {
          detail: store.getState().account_entry.selected_launch_id,
        })
      );
      return;
    }

    const sessionTarget = event.target.closest("[data-shell-session]");
    if (sessionTarget?.dataset.shellSession) {
      store.resumeSession(sessionTarget.dataset.shellSession);
      mountNode.dispatchEvent(
        new CustomEvent("shell:session-resume", {
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
    setEntryLaunch(launchId) {
      store.setEntryLaunch(launchId);
    },
    resumeSession(sessionId) {
      store.resumeSession(sessionId);
    },
    destroy() {
      unsubscribe();
      mountNode.removeEventListener("click", handleClick);
    },
  };
}
