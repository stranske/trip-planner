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
    if (selector === "[data-planner-section]" && this.dataset.plannerSection) {
      return this;
    }

    if (selector === "[data-planner-decision]" && this.dataset.plannerDecision) {
      return this;
    }

    if (selector === "[data-planner-response-action]" && this.dataset.plannerResponseAction) {
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
  inTripRevisionPromptScenario,
  inTripRevisionPromptState,
  leisureFeedbackLoopScenario,
  leisureFeedbackLoopState,
  plannerUiStateMocks,
} = await loadModule("bundle/planner/mock-state.js");
const {
  createPlannerSidePanelStore,
  renderComparablesDisplayComponent,
  renderJustificationBurdenComponent,
  renderNextStepActionsComponent,
  renderOptionFeedbackPromptsComponent,
  renderPendingDecisionsComponent,
  renderPolicyPostureDisplayComponent,
  renderProposalReadinessIndicatorComponent,
  renderPlannerOutputsDisplay,
  renderStructuredResponseCaptureComponent,
  renderPlannerSidePanel,
} = await loadModule("bundle/planner/side-panel.js");

const businessApprovalState = {
  ...leisureFeedbackLoopState,
  trip: {
    ...leisureFeedbackLoopState.trip,
    mode: "business",
    status: "booked",
    title: "Dallas client review with policy packet",
    summary: "The approval surface should summarize compliance posture before export.",
  },
  proposal: {
    proposal_id: "proposal-approval-01",
    comparables: [
      {
        category: "lodging",
        label: "Within-cap airport hotel",
        vendor: "Courtyard",
        booking_channel: "Concur",
        estimated_cost: {
          currency: "USD",
          typical_amount: 214,
        },
        notes: [
          "Requires a pre-dawn transfer to the client site.",
          "Stays within the standard nightly lodging cap.",
        ],
      },
      {
        category: "airfare",
        label: "One-stop daytime routing",
        vendor: "American",
        booking_channel: "Concur",
        estimated_cost: {
          currency: "USD",
          typical_amount: 386,
        },
        notes: ["Extends total travel time by nearly three hours."],
      },
    ],
    justifications: [
      {
        category: "lodging",
        summary: "Higher nightly rate keeps the team near the client site for a pre-dawn audit start.",
        evidence: [
          "Audit kickoff begins at 05:45 local time.",
          "The lower-cost hotel adds a 40-minute transfer each way.",
        ],
      },
      {
        category: "schedule",
        summary: "The selected hotel reduces fatigue risk across consecutive site inspections.",
        evidence: ["Traveler arrives after a late connection on the prior evening."],
      },
    ],
    approval_notes: [
      "Attach the lower-cost comparable to the approval packet.",
      "Reference the fatigue-management rationale in the manager request.",
    ],
    requested_exception: {
      exception_type: "lodging_rate_cap",
      reason: "Request an exception to preserve site access and reduce fatigue risk.",
      requested_approval_roles: ["manager", "finance"],
      notes: ["Document why the within-cap hotel materially degrades the operating schedule."],
    },
  },
  policy_evaluation: {
    evaluation_id: "eval-approval-01",
    proposal_id: "proposal-approval-01",
    status: "exception_required",
    approval_requirements: [
      {
        role: "manager",
        reason: "Operational exception requires manager approval",
        mandatory: true,
      },
      {
        role: "finance",
        reason: "Lodging cap exception requires finance review",
        mandatory: true,
      },
    ],
    failure_reasons: [
      {
        code: "lodging_rate_cap",
        message: "Selected lodging exceeds the nightly cap but includes an operational-safety justification.",
        severity: "warning",
        related_category: "lodging",
      },
    ],
    preferred_alternatives: [
      {
        category: "lodging",
        summary: "Use the attached lower-cost comparable if the exception is denied.",
        rationale: "Preserves site access with a lower nightly cost ceiling.",
        comparable_ref: "lodging",
      },
    ],
    exception_guidance: [
      "Retain the lower-cost comparable in the approval packet.",
      "Document the operational-safety rationale in the manager approval request.",
    ],
    notes: ["Proposal is exception-eligible if the fatigue-management rationale is approved."],
    compliance_score: 0.68,
  },
};

test("planner side panel store initializes with decision-focused UI state", () => {
  const store = createPlannerSidePanelStore(leisureFeedbackLoopState);
  const state = store.getState();

  assert.equal(state.ui.active_section, "decisions");
  assert.equal(state.ui.selected_decision_id, "lodging-signal");

  store.setActiveSection("options");
  assert.equal(store.getState().ui.active_section, "options");
});

test("planner UI mock catalog exposes the leisure feedback loop workflow state", () => {
  assert.equal(plannerUiStateMocks.leisure_feedback_loop, leisureFeedbackLoopScenario);
  assert.equal(leisureFeedbackLoopScenario.scenario_id, "leisure-feedback-loop");
  assert.match(leisureFeedbackLoopScenario.workflow, /Traveler compares lodging tradeoffs/);
  assert.match(leisureFeedbackLoopScenario.persona_summary, /walkability, food value/);
  assert.equal(leisureFeedbackLoopScenario.panel_state, leisureFeedbackLoopState);
  assert.equal(leisureFeedbackLoopScenario.panel_state.trip.mode, "leisure");
  assert.equal(leisureFeedbackLoopScenario.panel_state.pending_decisions[0].decision_id, "lodging-signal");
  assert.equal(leisureFeedbackLoopScenario.panel_state.next_step_actions[0].target_section, "decisions");
});

test("planner UI mock catalog exposes the in-trip revision prompt workflow state", () => {
  assert.equal(plannerUiStateMocks.in_trip_revision_prompt, inTripRevisionPromptScenario);
  assert.equal(inTripRevisionPromptScenario.scenario_id, "in-trip-revision-prompt");
  assert.match(inTripRevisionPromptScenario.workflow, /weather disrupts the next day/);
  assert.match(inTripRevisionPromptScenario.persona_summary, /Solo Kyoto trip/);
  assert.equal(inTripRevisionPromptScenario.panel_state, inTripRevisionPromptState);
  assert.equal(inTripRevisionPromptScenario.panel_state.trip.status, "in_trip");
  assert.equal(inTripRevisionPromptScenario.panel_state.option_set.purpose, "in_trip_revision");
  assert.equal(
    inTripRevisionPromptScenario.panel_state.pending_decisions[0].decision_id,
    "rain-replan-signal"
  );
  assert.equal(inTripRevisionPromptScenario.panel_state.next_step_actions[0].target_section, "decisions");
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

test("planner side panel renders the in-trip revision prompt scenario", () => {
  const mountNode = new FakeMountNode();
  const controller = renderPlannerSidePanel(mountNode, inTripRevisionPromptState);

  assert.match(mountNode.innerHTML, /Choose the revision style/);
  assert.match(mountNode.innerHTML, /what should the planner protect first/i);
  assert.match(mountNode.innerHTML, /Protect the booked anchor and make the rest easier\./);

  controller.setActiveSection("outputs");

  assert.match(mountNode.innerHTML, /Why the planner is asking now/);
  assert.match(mountNode.innerHTML, /revision only changes the surrounding neighborhood flow/i);

  controller.destroy();
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

test("structured response capture component renders all response actions per option", () => {
  const markup = renderStructuredResponseCaptureComponent(
    leisureFeedbackLoopState.option_set,
    leisureFeedbackLoopState.pending_decisions[0].decision_id
  );

  assert.match(markup, /aria-label="Structured response capture actions"/);
  assert.match(markup, /data-planner-response-action="accept"/);
  assert.match(markup, /data-planner-response-action="reject"/);
  assert.match(markup, /data-planner-response-action="revise"/);
  assert.match(markup, /data-planner-response-action="save_as_fallback"/);
  assert.match(markup, /data-planner-response-action="do_more_before_asking_again"/);
  assert.match(markup, /Save as fallback/);
  assert.match(markup, /Do more before asking again/);
});

test("structured response capture component renders an empty state when no options exist", () => {
  const markup = renderStructuredResponseCaptureComponent(
    { ...leisureFeedbackLoopState.option_set, options: [] },
    null
  );

  assert.match(markup, /No structured response actions available\./);
});

test("next-step actions component renders available traveler actions", () => {
  const markup = renderNextStepActionsComponent(
    leisureFeedbackLoopState.next_step_actions,
    "decisions"
  );

  assert.match(markup, /aria-label="Next-step actions"/);
  assert.match(markup, /data-planner-next-step="answer-lodging-signal"/);
  assert.match(markup, /data-planner-action-kind="answer_decision"/);
  assert.match(markup, /Answer the lodging decision/);
  assert.match(markup, /planner-next-step-card--primary is-contextual/);
  assert.match(markup, /Compare the lodging options again/);
});

test("next-step actions component renders an empty state when no actions exist", () => {
  const markup = renderNextStepActionsComponent([], "outputs");

  assert.match(markup, /No next-step actions available\./);
});

test("policy posture display component renders compliance status and approval details", () => {
  const markup = renderPolicyPostureDisplayComponent(businessApprovalState.policy_evaluation);

  assert.match(markup, /aria-label="Policy posture display"/);
  assert.match(markup, /data-policy-status="exception_required"/);
  assert.match(markup, /Compliance score: 68%/);
  assert.match(markup, /Operational exception requires manager approval/);
  assert.match(markup, /lodging.*operational-safety justification/s);
  assert.match(markup, /Retain the lower-cost comparable in the approval packet\./);
  assert.match(markup, /Proposal is exception-eligible if the fatigue-management rationale is approved\./);
});

test("policy posture display component renders an empty state when policy evaluation is absent", () => {
  const markup = renderPolicyPostureDisplayComponent(null);

  assert.match(markup, /Business approval-readiness is not active for this planner state\./);
});

test("comparables display component renders alternative options for approval review", () => {
  const markup = renderComparablesDisplayComponent(
    businessApprovalState.proposal,
    businessApprovalState.policy_evaluation
  );

  assert.match(markup, /aria-label="Comparable options"/);
  assert.match(markup, /data-planner-comparable-category="lodging"/);
  assert.match(markup, /Within-cap airport hotel/);
  assert.match(markup, /Courtyard via Concur/);
  assert.match(markup, /USD 214/);
  assert.match(markup, /Preferred fallback/);
  assert.match(markup, /Requires a pre-dawn transfer to the client site\./);
});

test("comparables display component renders an empty state when no alternatives exist", () => {
  const markup = renderComparablesDisplayComponent({ proposal_id: "proposal-empty", comparables: [] }, null);

  assert.match(markup, /No comparable options attached to this approval review\./);
});

test("justification burden component renders required documentation and approval packet context", () => {
  const markup = renderJustificationBurdenComponent(
    businessApprovalState.proposal,
    businessApprovalState.policy_evaluation
  );

  assert.match(markup, /aria-label="Justification burden"/);
  assert.match(markup, /data-justification-burden="summary"/);
  assert.match(markup, /Higher nightly rate keeps the team near the client site/);
  assert.match(markup, /Audit kickoff begins at 05:45 local time\./);
  assert.match(markup, /Attach the lower-cost comparable to the approval packet\./);
  assert.match(markup, /Request an exception to preserve site access and reduce fatigue risk\./);
  assert.match(markup, /lodging rate cap/);
  assert.match(markup, /manager/);
  assert.match(markup, /finance/);
});

test("justification burden component renders an empty state when no documentation burden exists", () => {
  const markup = renderJustificationBurdenComponent(
    { proposal_id: "proposal-empty", comparables: [] },
    null
  );

  assert.match(markup, /No justification burden is attached to this approval review\./);
});

test("proposal readiness indicator component renders readiness status and checklist", () => {
  const markup = renderProposalReadinessIndicatorComponent(
    businessApprovalState.proposal,
    businessApprovalState.policy_evaluation
  );

  assert.match(markup, /aria-label="Proposal readiness indicator"/);
  assert.match(markup, /data-proposal-readiness="exception-packet-ready"/);
  assert.match(markup, /4 of 4 approval checks complete\./);
  assert.match(markup, /aria-valuenow="100"/);
  assert.match(markup, /68% compliance/);
  assert.match(markup, /Ready:<\/strong> Comparables attached\. 2 options in the approval packet\./);
  assert.match(markup, /Ready:<\/strong> Submission path defined\. Exception request is attached\./);
});

test("proposal readiness indicator component renders an empty state when approval data is absent", () => {
  const markup = renderProposalReadinessIndicatorComponent(null, null);

  assert.match(markup, /No proposal readiness state is available for this planner review\./);
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

test("planner side panel approval section includes the policy posture display", () => {
  const mountNode = new FakeMountNode();
  const controller = renderPlannerSidePanel(mountNode, businessApprovalState);

  controller.setActiveSection("approval");

  assert.match(mountNode.innerHTML, /Proposal Readiness/);
  assert.match(mountNode.innerHTML, /exception packet ready/);
  assert.match(mountNode.innerHTML, /4 of 4 approval checks complete\./);
  assert.match(mountNode.innerHTML, /Policy posture/);
  assert.match(mountNode.innerHTML, /exception required/);
  assert.match(mountNode.innerHTML, /Compliance score: 68%/);
  assert.match(mountNode.innerHTML, /Justification Burden/);
  assert.match(mountNode.innerHTML, /Documentation burden/);
  assert.match(mountNode.innerHTML, /Request an exception to preserve site access and reduce fatigue risk\./);
  assert.match(mountNode.innerHTML, /Preferred alternatives/);
  assert.match(mountNode.innerHTML, /Comparables/);
  assert.match(mountNode.innerHTML, /Within-cap airport hotel/);

  controller.destroy();
});

test("planner side panel emits a typed accept response event", () => {
  const mountNode = new FakeMountNode();
  const controller = renderPlannerSidePanel(mountNode, leisureFeedbackLoopState);

  controller.setActiveSection("options");
  mountNode.click(
    new FakeButton({
      plannerResponseAction: "accept",
      plannerOptionId: "option-bairro-alto",
      plannerDecisionId: "lodging-signal",
    })
  );

  assert.equal(mountNode.dispatchedEvents[0].type, "planner-response-accept");
  assert.deepEqual(mountNode.dispatchedEvents[0].detail, {
    action_type: "accept",
    trip_id: "trip-leisure-lisbon-oct",
    option_set_id: "option-set-lodging-01",
    option_id: "option-bairro-alto",
    decision_id: "lodging-signal",
    source_section: "options",
    accepted_option_id: "option-bairro-alto",
  });

  controller.destroy();
});

test("planner side panel emits a typed reject response event", () => {
  const mountNode = new FakeMountNode();
  const controller = renderPlannerSidePanel(mountNode, leisureFeedbackLoopState);

  controller.setActiveSection("options");
  mountNode.click(
    new FakeButton({
      plannerResponseAction: "reject",
      plannerOptionId: "option-bairro-alto",
      plannerDecisionId: "lodging-signal",
    })
  );

  assert.equal(mountNode.dispatchedEvents[0].type, "planner-response-reject");
  assert.deepEqual(mountNode.dispatchedEvents[0].detail, {
    action_type: "reject",
    trip_id: "trip-leisure-lisbon-oct",
    option_set_id: "option-set-lodging-01",
    option_id: "option-bairro-alto",
    decision_id: "lodging-signal",
    source_section: "options",
    rejected_option_id: "option-bairro-alto",
  });

  controller.destroy();
});

test("planner side panel emits a typed revise response event", () => {
  const mountNode = new FakeMountNode();
  const controller = renderPlannerSidePanel(mountNode, leisureFeedbackLoopState);

  controller.setActiveSection("options");
  mountNode.click(
    new FakeButton({
      plannerResponseAction: "revise",
      plannerOptionId: "option-bairro-alto",
      plannerDecisionId: "lodging-signal",
    })
  );

  assert.equal(mountNode.dispatchedEvents[0].type, "planner-response-revise");
  assert.deepEqual(mountNode.dispatchedEvents[0].detail, {
    action_type: "revise",
    trip_id: "trip-leisure-lisbon-oct",
    option_set_id: "option-set-lodging-01",
    option_id: "option-bairro-alto",
    decision_id: "lodging-signal",
    source_section: "options",
    revision_target: {
      option_id: "option-bairro-alto",
      decision_id: "lodging-signal",
    },
  });

  controller.destroy();
});

test("planner side panel emits a typed save-as-fallback response event", () => {
  const mountNode = new FakeMountNode();
  const controller = renderPlannerSidePanel(mountNode, leisureFeedbackLoopState);

  controller.setActiveSection("options");
  mountNode.click(
    new FakeButton({
      plannerResponseAction: "save_as_fallback",
      plannerOptionId: "option-bairro-alto",
      plannerDecisionId: "lodging-signal",
    })
  );

  assert.equal(mountNode.dispatchedEvents[0].type, "planner-response-save-as-fallback");
  assert.deepEqual(mountNode.dispatchedEvents[0].detail, {
    action_type: "save_as_fallback",
    trip_id: "trip-leisure-lisbon-oct",
    option_set_id: "option-set-lodging-01",
    option_id: "option-bairro-alto",
    decision_id: "lodging-signal",
    source_section: "options",
    fallback_option_id: "option-bairro-alto",
  });

  controller.destroy();
});

test("planner side panel emits a typed do-more-before-asking-again response event", () => {
  const mountNode = new FakeMountNode();
  const controller = renderPlannerSidePanel(mountNode, leisureFeedbackLoopState);

  controller.setActiveSection("options");
  mountNode.click(
    new FakeButton({
      plannerResponseAction: "do_more_before_asking_again",
      plannerOptionId: "option-bairro-alto",
      plannerDecisionId: "lodging-signal",
    })
  );

  assert.equal(
    mountNode.dispatchedEvents[0].type,
    "planner-response-do-more-before-asking-again"
  );
  assert.deepEqual(mountNode.dispatchedEvents[0].detail, {
    action_type: "do_more_before_asking_again",
    trip_id: "trip-leisure-lisbon-oct",
    option_set_id: "option-set-lodging-01",
    option_id: "option-bairro-alto",
    decision_id: "lodging-signal",
    source_section: "options",
    deferred_option_id: "option-bairro-alto",
    requested_follow_up: "do_more_before_asking_again",
  });

  controller.destroy();
});

test("planner side panel includes the next-step actions section", () => {
  const mountNode = new FakeMountNode();
  const controller = renderPlannerSidePanel(mountNode, leisureFeedbackLoopState);

  assert.match(mountNode.innerHTML, /Next-Step Actions/);
  assert.match(mountNode.innerHTML, /Answer the lodging decision/);
  assert.match(mountNode.innerHTML, /Compare the lodging options again/);

  controller.setActiveSection("options");

  assert.match(mountNode.innerHTML, /planner-next-step-card--secondary is-contextual/);

  controller.destroy();
});
