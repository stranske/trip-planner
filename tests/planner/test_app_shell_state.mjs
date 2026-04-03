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
    if (selector === "[data-shell-route]" && this.dataset.shellRoute) {
      return this;
    }

    if (selector === "[data-shell-trip]" && this.dataset.shellTrip) {
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
  signedInDashboardShellState,
  activeLeisureTripShellState,
  activeBusinessTripShellState,
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
  assert.equal(appShellStateMocks.signed_in_dashboard, signedInDashboardShellState);
  assert.equal(appShellStateMocks.active_leisure_trip, activeLeisureTripShellState);
  assert.equal(appShellStateMocks.active_business_trip, activeBusinessTripShellState);
});

test("app shell derives a dashboard route when no active trip is selected", () => {
  const state = buildAppShellState(signedInDashboardShellState);

  assert.equal(state.active_route, "dashboard");
  assert.equal(state.active_trip_id, "trip-leisure-lisbon-oct");
  assert.match(renderAppShellLayout(state), /Signed-in planning home/);
  assert.match(renderAppShellLayout(state), /Seattle audit trip with approval packet/);
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

  store.setRoute("approval_center");
  assert.equal(store.getState().active_route, "approval_center");
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
