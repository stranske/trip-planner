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
const {
  createPlannerSidePanelStore,
  renderOptionFeedbackPromptsComponent,
  renderPendingDecisionsComponent,
  renderPlannerOutputsDisplay,
  renderPlannerSidePanel,
} = await loadModule("bundle/planner/side-panel.js");

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

test("option feedback prompts component renders collection fields and pacing suggestions", () => {
  const markup = renderOptionFeedbackPromptsComponent(
    leisureFeedbackLoopState.option_set,
    leisureFeedbackLoopState.planner_behavior
  );

  assert.match(markup, /aria-label="Option feedback prompts"/);
  assert.match(markup, /data-planner-option-feedback="option-bairro-alto"/);
  assert.match(markup, /What feels strongest about this option\?/);
  assert.match(markup, /What should the planner change if this misses\?/);
  assert.match(markup, /Show options even sooner/);
  assert.match(markup, /Do more before asking again/);
  assert.match(markup, /Explain less/);
});

test("option feedback prompts component renders an empty state when no options exist", () => {
  const markup = renderOptionFeedbackPromptsComponent(
    { ...leisureFeedbackLoopState.option_set, options: [] },
    leisureFeedbackLoopState.planner_behavior
  );

  assert.match(markup, /No option feedback prompts yet\./);
});

test("pending decisions component renders the default decision prompt and choices", () => {
  const markup = renderPendingDecisionsComponent(leisureFeedbackLoopState.pending_decisions);

  assert.match(markup, /aria-label="Pending decisions"/);
  assert.match(markup, /Choose the better base camp/);
  assert.match(markup, /Which tradeoff feels more like the trip you want\?/);
  assert.match(markup, /Stay central and accept tighter rooms\./);
  assert.match(markup, /Prioritize recovery quiet and a little extra transit\./);
  assert.match(markup, /planner-decision-link is-active/);
});

test("pending decisions component respects explicit decision selection when multiple prompts exist", () => {
  const markup = renderPendingDecisionsComponent(
    [
      ...leisureFeedbackLoopState.pending_decisions,
      {
        decision_id: "pace-signal",
        title: "Choose the first full-day pace",
        prompt: "How much structure should Day 2 have after arrival?",
        choices: ["Keep it open until lunch.", "Lock in one museum and one long dinner."],
      },
    ],
    "pace-signal"
  );

  assert.match(markup, /Choose the first full-day pace/);
  assert.match(markup, /How much structure should Day 2 have after arrival\?/);
  assert.match(markup, /Lock in one museum and one long dinner\./);
  assert.doesNotMatch(markup, /Which tradeoff feels more like the trip you want\?/);
});

test("pending decisions component renders an empty state when no prompts exist", () => {
  const markup = renderPendingDecisionsComponent([]);

  assert.match(markup, /No pending decisions\./);
});

test("planner side panel options section includes the option feedback prompts surface", () => {
  const mountNode = new FakeMountNode();
  const controller = renderPlannerSidePanel(mountNode, leisureFeedbackLoopState);

  controller.setActiveSection("options");

  assert.match(mountNode.innerHTML, /Stay shape for the first half of the trip/);
  assert.match(mountNode.innerHTML, /What feels strongest about this option\?/);
  assert.match(mountNode.innerHTML, /data-planner-feedback-kind="show_options_sooner"/);

  controller.destroy();
});
