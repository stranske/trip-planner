import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import url from "node:url";

const __dirname = path.dirname(url.fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");

class FakeElement {}
class FakeHTMLElement extends FakeElement {}

globalThis.Element = FakeElement;
globalThis.HTMLElement = FakeHTMLElement;

class FakeMountNode extends FakeHTMLElement {
  constructor() {
    super();
    this.innerHTML = "";
    this.listeners = new Map();
    this.dispatchedEvents = [];
  }

  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }

  removeEventListener(type, listener) {
    if (this.listeners.get(type) === listener) {
      this.listeners.delete(type);
    }
  }

  click(target) {
    const listener = this.listeners.get("click");
    if (listener) {
      listener({ target });
    }
  }

  dispatchEvent(event) {
    this.dispatchedEvents.push(event);
    return true;
  }
}

class FakeButton extends FakeHTMLElement {
  constructor(dataset) {
    super();
    this.dataset = dataset;
  }

  closest(selector) {
    if (
      (selector === "[data-shell-route]" || selector === "button[data-shell-route]") &&
      this.dataset.shellRoute
    ) {
      return this;
    }

    if (selector === "[data-shell-trip]" && this.dataset.shellTrip) {
      return this;
    }

    if (selector === "[data-shell-launch]" && this.dataset.shellLaunch) {
      return this;
    }

    if (selector === "[data-shell-session]" && this.dataset.shellSession) {
      return this;
    }

    if (
      selector === "[data-shell-visualization-scenario]" &&
      this.dataset.shellVisualizationScenario
    ) {
      return this;
    }

    return null;
  }
}

class FakeCustomEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
}

globalThis.CustomEvent = FakeCustomEvent;

async function loadModule(relativePath) {
  const source = await fs.readFile(path.join(repoRoot, relativePath), "utf8");
  return import(`data:text/javascript,${encodeURIComponent(source)}`);
}

const {
  appShellStateMocks,
  firstTimeLeisureDashboardShellState,
  signedInDashboardShellState,
  businessPolicyStartDashboardShellState,
  activeLeisureTripShellState,
  activeBusinessTripShellState,
  inTripRevisionShellState,
} = await loadModule("bundle/app-shell/mock-state.js");
const {
  buildAppShellState,
  createAppShellStore,
  getShellRoutes,
  renderAppShell,
  renderAppShellLayout,
  renderWorkspaceStatusBoundary,
} = await loadModule("bundle/app-shell/app-shell.js");

test("app shell mock catalog exposes signed-in, leisure, and business contexts", () => {
  assert.equal(
    appShellStateMocks.first_time_leisure_dashboard,
    firstTimeLeisureDashboardShellState
  );
  assert.equal(appShellStateMocks.signed_in_dashboard, signedInDashboardShellState);
  assert.equal(
    appShellStateMocks.business_policy_start_dashboard,
    businessPolicyStartDashboardShellState
  );
  assert.equal(appShellStateMocks.active_leisure_trip, activeLeisureTripShellState);
  assert.equal(appShellStateMocks.active_business_trip, activeBusinessTripShellState);
  assert.equal(appShellStateMocks.in_trip_revision, inTripRevisionShellState);
});

test("app shell derives a dashboard route when no active trip is selected", () => {
  const state = buildAppShellState(signedInDashboardShellState);

  assert.equal(state.active_route, "dashboard");
  assert.equal(state.active_trip_id, "trip-leisure-lisbon-oct");
  assert.equal(state.account_entry.selected_launch_id, "resume_existing_trip");
  assert.match(renderAppShellLayout(state), /Signed-in planning home/);
  assert.match(renderAppShellLayout(state), /Seattle audit trip with approval packet/);
});

test("first-time leisure entry defaults to a new leisure launch", () => {
  const state = buildAppShellState(firstTimeLeisureDashboardShellState);

  assert.equal(state.account_entry.selected_launch_id, "new_leisure_trip");
  assert.match(renderAppShellLayout(state), /Trip entry is ready for first use/);
  assert.match(renderAppShellLayout(state), /Start a new leisure trip/);
  assert.match(renderAppShellLayout(state), /No saved trips yet/);
});

test("shell routes stay mode-aware for leisure and business trips", () => {
  const leisureRoutes = getShellRoutes(
    activeLeisureTripShellState.trips[0],
    activeLeisureTripShellState.workspace
  );
  const businessRoutes = getShellRoutes(
    activeBusinessTripShellState.trips[1],
    activeBusinessTripShellState.workspace
  );

  assert.deepEqual(
    leisureRoutes.map((route) => route.route_id),
    ["dashboard", "trip_workspace", "planner_workspace"]
  );
  assert.deepEqual(
    businessRoutes.map((route) => route.route_id),
    ["dashboard", "trip_workspace", "planner_workspace", "approval_center"]
  );
});

test("workspace status boundary renders deterministic loading and error copy", () => {
  assert.match(
    renderWorkspaceStatusBoundary({
      ...activeLeisureTripShellState.workspace,
      status: "loading",
      loading_message: "Hydrating saved scenarios from persistence.",
    }),
    /Hydrating saved scenarios from persistence/
  );
  assert.match(
    renderWorkspaceStatusBoundary({
      ...activeLeisureTripShellState.workspace,
      status: "error",
      error_message: "Scenario state drifted out of sync.",
    }),
    /Scenario state drifted out of sync/
  );
});

test("app shell store updates route and active trip while preserving visible shell output", () => {
  const store = createAppShellStore(signedInDashboardShellState);

  store.setActiveTrip("trip-client-audit-sea");
  assert.equal(store.getState().active_trip_id, "trip-client-audit-sea");
  assert.equal(store.getState().workspace.trip_id, "trip-client-audit-sea");
  assert.equal(store.getState().workspace.status, "empty");
  assert.equal(store.getState().workspace.planner_panel_state, null);
  assert.deepEqual(store.getState().workspace.scenario_summaries, []);
  assert.deepEqual(store.getState().workspace.checkpoint_history, []);
  assert.equal(store.getState().workspace.budget_summary, null);

  store.setRoute("approval_center");
  assert.equal(store.getState().active_route, "approval_center");
});

test("entry store switches launch flows and resumes saved sessions", () => {
  const store = createAppShellStore(signedInDashboardShellState);

  store.setEntryLaunch("new_business_trip");
  assert.equal(store.getState().account_entry.selected_launch_id, "new_business_trip");

  store.resumeSession("session-business-audit-approval");
  assert.equal(store.getState().active_trip_id, "trip-client-audit-sea");
  assert.equal(store.getState().active_route, "approval_center");
  assert.equal(store.getState().workspace.status, "loading");
  assert.equal(
    store.getState().workspace.loading_message,
    "Rehydrating the saved session entry point."
  );
  assert.deepEqual(store.getState().workspace.visualization_scenarios, []);
  assert.equal(store.getState().workspace.active_visualization_scenario_id, null);
});

test("entry store reports a deterministic error for missing sessions", () => {
  const store = createAppShellStore(firstTimeLeisureDashboardShellState);

  store.resumeSession("missing-session");
  assert.equal(store.getState().active_route, "dashboard");
  assert.equal(store.getState().workspace.status, "error");
  assert.equal(
    store.getState().workspace.error_message,
    "Selected session is no longer available."
  );
});

test("mounted app shell rerenders on route and trip changes", () => {
  const mountNode = new FakeMountNode();
  const controller = renderAppShell(mountNode, activeBusinessTripShellState);

  assert.match(mountNode.innerHTML, /Approval posture/);
  assert.equal(controller.getState().active_trip_id, "trip-client-audit-sea");

  mountNode.click(new FakeButton({ shellRoute: "planner_workspace" }));
  assert.equal(controller.getState().active_route, "planner_workspace");
  assert.match(mountNode.innerHTML, /Immediate actions/);

  mountNode.click(new FakeButton({ shellRoute: "approval_center" }));
  assert.equal(controller.getState().active_route, "approval_center");
  assert.match(mountNode.innerHTML, /travel_ops: Hotel zone exception/);

  controller.destroy();
  assert.equal(mountNode.listeners.has("click"), false);
});

test("mounted dashboard rerenders on launch and session entry interactions", () => {
  const mountNode = new FakeMountNode();
  const controller = renderAppShell(mountNode, signedInDashboardShellState);

  assert.match(mountNode.innerHTML, /Resume an existing trip/);

  mountNode.click(new FakeButton({ shellLaunch: "new_business_trip" }));
  assert.equal(controller.getState().account_entry.selected_launch_id, "new_business_trip");
  assert.match(
    mountNode.innerHTML,
    /Hotel zone, approval roles, and spend posture should be seeded/
  );

  mountNode.click(new FakeButton({ shellSession: "session-leisure-lisbon-planner" }));
  assert.equal(controller.getState().active_trip_id, "trip-leisure-lisbon-oct");
  assert.equal(controller.getState().active_route, "planner_workspace");
  assert.equal(controller.getState().workspace.status, "loading");
});

test("trip workspace renders scenario, checkpoint, and budget surfaces for leisure and business contexts", () => {
  const leisureWorkspace = renderAppShellLayout(
    buildAppShellState(activeLeisureTripShellState)
  );
  const businessWorkspace = renderAppShellLayout(
    buildAppShellState({
      ...activeBusinessTripShellState,
      active_route: "trip_workspace",
    })
  );

  assert.match(leisureWorkspace, /Scenario comparison/);
  assert.match(leisureWorkspace, /Central Lisbon base/);
  assert.match(leisureWorkspace, /Quiet riverside fallback/);
  assert.match(leisureWorkspace, /Budget posture/);
  assert.match(leisureWorkspace, /\$90 under target/);

  assert.match(businessWorkspace, /Primary exception-ready scenario/);
  assert.match(businessWorkspace, /Compliant downtown fallback/);
  assert.match(businessWorkspace, /Approval-ready lodging set/);
  assert.match(businessWorkspace, /\$40 under target before exception review/);
});

test("trip workspace can render an in-trip revised scenario without losing saved history", () => {
  const revisedWorkspace = renderAppShellLayout(
    buildAppShellState(inTripRevisionShellState)
  );

  assert.match(revisedWorkspace, /Rain-adjusted active plan/);
  assert.match(revisedWorkspace, /In-trip replanning checkpoint/);
  assert.match(revisedWorkspace, /\$145 over target unless the revised scenario holds/);
});

test("trip workspace renders map and timeline surfaces for route alternatives", () => {
  const rendered = renderAppShellLayout(activeLeisureTripShellState);

  assert.match(rendered, /Scenario route alternatives/);
  assert.match(rendered, /Scenario map surface/);
  assert.match(rendered, /Timeline structure/);
  assert.match(rendered, /Lisbon regional loop/);
  assert.match(rendered, /Scenic transit variant/);
  assert.match(rendered, /Sintra day cluster/);
  assert.match(rendered, /Day 3 Sintra excursion/);
});

test("planner workspace surfaces route coherence warnings from the selected visualization scenario", () => {
  const rendered = renderAppShellLayout({
    ...activeLeisureTripShellState,
    active_route: "planner_workspace",
  });

  assert.match(rendered, /Route coherence and burden/);
  assert.match(rendered, /Best route coherence with one medium-transfer excursion day/);
  assert.match(rendered, /Sintra day can stack hill fatigue after a late arrival evening/);
});

test("mounted app shell can switch between visualization scenarios", () => {
  const mountNode = new FakeMountNode();
  const controller = renderAppShell(mountNode, activeLeisureTripShellState);

  assert.equal(
    controller.getState().workspace.active_visualization_scenario_id,
    "scenario-lisbon-regional-loop"
  );
  assert.match(mountNode.innerHTML, /Lisbon regional loop/);
  assert.match(mountNode.innerHTML, /Sintra day cluster/);
  assert.match(
    mountNode.innerHTML,
    /data-shell-visualization-scenario="scenario-lisbon-regional-loop"[^>]*aria-pressed="true"/
  );
  assert.match(
    mountNode.innerHTML,
    /data-shell-visualization-scenario="scenario-lisbon-scenic-transit"[^>]*aria-pressed="false"/
  );

  mountNode.click(
    new FakeButton({
      shellVisualizationScenario: "scenario-lisbon-scenic-transit",
    })
  );

  assert.equal(
    controller.getState().workspace.active_visualization_scenario_id,
    "scenario-lisbon-scenic-transit"
  );
  assert.match(mountNode.innerHTML, /Scenic transit variant/);
  assert.match(mountNode.innerHTML, /River ferry stitch/);
  assert.match(
    mountNode.innerHTML,
    /data-shell-visualization-scenario="scenario-lisbon-scenic-transit"[^>]*aria-pressed="true"/
  );
  assert.match(mountNode.innerHTML, /shell-mode-pill--leisure/);
});

test("trip workspace keeps scenario switcher mode aligned to the active business trip", () => {
  const rendered = renderAppShellLayout({
    ...activeBusinessTripShellState,
    active_route: "trip_workspace",
  });

  assert.match(rendered, /shell-mode-pill--business/);
  assert.match(rendered, /aria-pressed="true"/);
  assert.match(rendered, /shell-mode-pill--business">business base route/);
});

test("trip workspace falls back to textual guidance when map data is missing", () => {
  const rendered = renderAppShellLayout({
    ...activeLeisureTripShellState,
    workspace: {
      ...activeLeisureTripShellState.workspace,
      visualization_scenarios: [],
      active_visualization_scenario_id: null,
    },
  });

  assert.match(rendered, /missing route visualization payload/);
  assert.match(
    rendered,
    /Map provider data is unavailable, so the shell should fall back to textual route summaries/
  );
});

test("mounted app shell ignores click events from non-element targets", () => {
  const mountNode = new FakeMountNode();
  const controller = renderAppShell(mountNode, activeBusinessTripShellState);

  mountNode.click({});
  assert.equal(controller.getState().active_route, "approval_center");
});

test("app shell layout escapes user-provided HTML-sensitive content", () => {
  const rendered = renderAppShellLayout(
    buildAppShellState({
      ...activeBusinessTripShellState,
      active_route: "dashboard",
      session: {
        ...activeBusinessTripShellState.session,
        display_name: "<Admin>",
        organization: "Ops & Risk",
      },
      workspace: {
        ...activeBusinessTripShellState.workspace,
        persistence_summary: ["Line <b>bold</b> & ready"],
      },
      trips: activeBusinessTripShellState.trips.map((trip, index) =>
        index === 1
          ? {
              ...trip,
              title: "<script>alert(1)</script>",
              summary: "Line <b>bold</b> & ready",
            }
          : trip
      ),
    })
  );

  assert.match(rendered, /&lt;Admin&gt;/);
  assert.match(rendered, /Ops &amp; Risk/);
  assert.match(rendered, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(rendered, /Line &lt;b&gt;bold&lt;\/b&gt; &amp; ready/);
  assert.doesNotMatch(rendered, /<script>alert\(1\)<\/script>/);
});
