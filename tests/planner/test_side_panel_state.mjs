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
}

class FakeButton extends FakeHTMLElement {
  constructor(dataset) {
    super();
    this.dataset = dataset;
  }

  closest(selector) {
    if (selector === "[data-planner-section]" && this.dataset.plannerSection) {
      return this;
    }

    if (selector === "[data-planner-decision]" && this.dataset.plannerDecision) {
      return this;
    }

    return null;
  }
}

async function loadModule(relativePath) {
  const source = await fs.readFile(path.join(repoRoot, relativePath), "utf8");
  return import(`data:text/javascript,${encodeURIComponent(source)}`);
}

const { leisureFeedbackLoopState } = await loadModule("bundle/planner/mock-state.js");
const { createPlannerSidePanelStore, renderPlannerOutputsDisplay, renderPlannerSidePanel } = await loadModule(
  "bundle/planner/side-panel.js"
);

test("planner side panel store initializes with decision-focused UI state", () => {
  const store = createPlannerSidePanelStore(leisureFeedbackLoopState);
  const state = store.getState();

  assert.equal(state.ui.active_section, "decisions");
  assert.equal(state.ui.selected_decision_id, "lodging-signal");

  store.setActiveSection("options");
  assert.equal(store.getState().ui.active_section, "options");
});

test("planner side panel controller rerenders on section and decision changes", () => {
  const mountNode = new FakeMountNode();
  const controller = renderPlannerSidePanel(mountNode, leisureFeedbackLoopState);

  assert.match(mountNode.innerHTML, /Pending Decisions/);
  assert.match(mountNode.innerHTML, /Choose the better base camp/);

  mountNode.click(new FakeButton({ plannerSection: "outputs" }));
  assert.equal(controller.getState().ui.active_section, "outputs");
  assert.match(mountNode.innerHTML, /Planner read/);

  mountNode.click(new FakeButton({ plannerDecision: "lodging-signal" }));
  assert.equal(controller.getState().ui.active_section, "decisions");
  assert.equal(controller.getState().ui.selected_decision_id, "lodging-signal");
  assert.match(mountNode.innerHTML, /Which tradeoff feels more like the trip you want\?/);

  controller.destroy();
  assert.equal(mountNode.listeners.has("click"), false);
});

test("planner outputs display renders messages and output metadata", () => {
  const markup = renderPlannerOutputsDisplay(leisureFeedbackLoopState.outputs);

  assert.match(markup, /aria-label="Planner outputs"/);
  assert.match(markup, /data-planner-output-id="summary-01"/);
  assert.match(markup, /Planner read/);
  assert.match(markup, /quality where it changes the day/);
  assert.match(markup, /feedback-loop/);
});

test("planner outputs display renders an empty state when no outputs exist", () => {
  const markup = renderPlannerOutputsDisplay([]);

  assert.match(markup, /No planner outputs yet\./);
});
