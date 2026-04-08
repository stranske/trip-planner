/**
 * @import {
 *   NextStepActionRecord,
 *   OptionSetRecord,
 *   PendingDecisionRecord,
 *   PlannerBehaviorRecord,
 *   PlannerOutputRecord,
 *   PlannerPanelState,
 *   PolicyEvaluationRecord,
 *   ProposalRecord,
 * } from "./orchestration-contracts"
 */

const PANEL_SECTIONS = /** @type {const} */ (["outputs", "decisions", "options", "approval"]);

/**
 * @param {PlannerPanelState} state
 * @returns {PlannerPanelSection}
 */
function getInitialActiveSection(state) {
  if (state.pending_decisions.length) {
    return "decisions";
  }

  if (state.outputs.length) {
    return "outputs";
  }

  if (state.option_set.options.length) {
    return "options";
  }

  return "approval";
}

/**
 * @param {PlannerPanelState} state
 * @returns {string | null}
 */
function getInitialDecisionId(state) {
  return state.pending_decisions[0]?.decision_id ?? null;
}

/**
 * @typedef {"outputs" | "decisions" | "options" | "approval"} PlannerPanelSection
 */

/**
 * @typedef {Object} PlannerPanelUiState
 * @property {PlannerPanelSection} active_section
 * @property {string | null} selected_decision_id
 */

/**
 * @typedef {Object} PlannerPanelViewState
 * @property {PlannerPanelState} data
 * @property {PlannerPanelUiState} ui
 */

/**
 * @typedef {"accept" | "reject" | "revise" | "save_as_fallback" | "do_more_before_asking_again"} StructuredResponseActionKind
 */

/**
 * @typedef {Object} StructuredResponseBaseDetail
 * @property {StructuredResponseActionKind} action_type
 * @property {string} trip_id
 * @property {string} option_set_id
 * @property {string} option_id
 * @property {string | null} decision_id
 * @property {"options"} source_section
 */

/**
 * @param {PlannerPanelState} state
 * @returns {PlannerPanelViewState}
 */
function createInitialViewState(state) {
  return {
    data: state,
    ui: {
      active_section: getInitialActiveSection(state),
      selected_decision_id: getInitialDecisionId(state),
    },
  };
}

/**
 * @param {PlannerPanelSection} section
 * @returns {string}
 */
function formatSectionLabel(section) {
  if (section === "approval") {
    return "Approval Readiness";
  }

  if (section === "options") {
    return "Option Set";
  }

  if (section === "decisions") {
    return "Pending Decisions";
  }

  return "Outputs";
}

/**
 * @param {string} value
 * @returns {string}
 */
function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/**
 * @param {string} value
 * @returns {string}
 */
function escapeAttribute(value) {
  return escapeHtml(value);
}

/**
 * @param {import("./orchestration-contracts").PlannerOutputRecord["status"] | string | undefined} status
 * @returns {"positive" | "caution" | "critical" | "neutral"}
 */
function normalizeOutputStatusTone(status) {
  if (status === "positive" || status === "caution" || status === "critical") {
    return status;
  }

  return "neutral";
}

/**
 * @param {PlannerPanelSection} section
 * @returns {string}
 */
function getSectionTabId(section) {
  return `planner-section-tab-${section}`;
}

/**
 * @param {PlannerPanelSection} section
 * @returns {string}
 */
function getSectionPanelId(section) {
  return `planner-section-panel-${section}`;
}

/**
 * @param {PlannerBehaviorRecord} behavior
 * @returns {string}
 */
function renderBehaviorSummary(behavior) {
  return `
    <section class="planner-behavior-card" aria-label="Planner behavior guidance">
      <div class="planner-section-header">
        <h3>Planner State</h3>
        <span class="planner-meta">${behavior.trip_stage}</span>
      </div>
      <div class="planner-chip-row">
        <span class="planner-chip">${behavior.target_research_passes} research passes</span>
        <span class="planner-chip">${behavior.target_options_before_checkpoint} options before check-in</span>
        <span class="planner-chip">${behavior.explanation_density} explanation</span>
      </div>
      <p class="planner-behavior-copy">
        ${behavior.ask_before_next_major_change ? "Ask before major route changes." : "Planner can advance without a checkpoint."}
        ${behavior.surface_options_early ? " Surface concrete options early." : " Hold options until more research is complete."}
      </p>
    </section>
  `;
}

/**
 * @param {PlannerPanelViewState} state
 * @returns {string}
 */
function renderSummaryCards(state) {
  const { trip } = state.data;
  const { duration_days: durationDays, primary_regions: primaryRegions, traveler_party: travelerParty } =
    trip.trip_frame;

  return `
    <div class="hero-summary-grid">
      <article class="summary-card">
        <strong>${trip.mode}</strong>
        <span>${trip.title}</span>
      </article>
      <article class="summary-card">
        <strong>${durationDays ?? "Flexible"} days</strong>
        <span>${primaryRegions.join(" · ") || "Region still settling"}</span>
      </article>
      <article class="summary-card">
        <strong>${travelerParty.traveler_count} traveler${travelerParty.traveler_count > 1 ? "s" : ""}</strong>
        <span>${travelerParty.kind}${travelerParty.notes ? ` · ${travelerParty.notes}` : ""}</span>
      </article>
    </div>
  `;
}

/**
 * @param {PlannerPanelViewState} state
 * @returns {string}
 */
function renderSectionTabs(state) {
  const counts = {
    outputs: state.data.outputs.length,
    decisions: state.data.pending_decisions.length,
    options: state.data.option_set.options.length,
    approval: state.data.policy_evaluation ? 1 : 0,
  };

  return `
    <nav class="planner-tab-list" aria-label="Planner panel sections" role="tablist">
      ${PANEL_SECTIONS.map(
        (section) => `
          <button
            type="button"
            class="planner-tab${state.ui.active_section === section ? " is-active" : ""}"
            data-planner-section="${section}"
            id="${getSectionTabId(section)}"
            role="tab"
            aria-selected="${state.ui.active_section === section}"
            aria-controls="${getSectionPanelId(section)}"
            tabindex="${state.ui.active_section === section ? "0" : "-1"}"
          >
            <span>${formatSectionLabel(section)}</span>
            <span class="planner-tab-count">${counts[section]}</span>
          </button>
        `
      ).join("")}
    </nav>
  `;
}

/**
 * @param {PlannerPanelSection} section
 * @param {PlannerPanelViewState} state
 * @returns {string}
 */
function renderSectionContent(section, state) {
  if (section === "decisions") {
    return renderPendingDecisions(state);
  }

  if (section === "options") {
    return renderOptions(state);
  }

  if (section === "approval") {
    return renderPolicyStatus(state);
  }

  return renderOutputs(state);
}

/**
 * @param {PlannerOutputRecord[]} outputs
 * @returns {string}
 */
export function renderPlannerOutputsDisplay(outputs) {
  if (!outputs.length) {
    return '<p class="planner-empty-state">No planner outputs yet.</p>';
  }

  return `
    <div class="planner-output-feed" role="list" aria-label="Planner outputs">
      ${outputs
    .map(
      (output) => {
        const escapedOutputId = escapeAttribute(output.output_id);
        const escapedTitle = escapeHtml(output.title);
        const escapedBody = escapeHtml(output.body);
        const escapedHighlights =
          output.highlights?.map((highlight) => `<li>${escapeHtml(highlight)}</li>`).join("") ?? "";
        const escapedTags =
          output.tags.map((tag) => `<span class="planner-chip">${escapeHtml(tag)}</span>`).join("");
        const statusTone = normalizeOutputStatusTone(output.status);
        const escapedStatusLabel = output.status ? escapeHtml(output.status) : "";

        return `
        <article class="planner-output-card" role="listitem" data-planner-output-id="${escapedOutputId}">
          <div class="planner-section-header">
            <h4>${escapedTitle}</h4>
            ${
              output.status
                ? `<span class="planner-status-pill planner-status-pill--${statusTone}">${escapedStatusLabel}</span>`
                : '<span class="planner-meta">message</span>'
            }
          </div>
          <p>${escapedBody}</p>
          ${
            output.highlights?.length
              ? `
                <ul class="planner-list" aria-label="Planner output highlights">
                  ${escapedHighlights}
                </ul>
              `
              : ""
          }
          ${
            output.tags.length
              ? `
                <div class="planner-chip-row" aria-label="Output tags">
                  ${escapedTags}
                </div>
              `
              : ""
          }
        </article>
      `
      }
    )
    .join("")}
    </div>
  `;
}

/**
 * @param {PlannerPanelViewState} state
 * @returns {string}
 */
function renderOutputs(state) {
  return renderPlannerOutputsDisplay(state.data.outputs);
}

/**
 * @param {PendingDecisionRecord[]} pendingDecisions
 * @param {string | null} selectedDecisionId
 * @returns {string}
 */
export function renderPendingDecisionsComponent(pendingDecisions, selectedDecisionId = null) {
  if (!pendingDecisions.length) {
    return '<p class="planner-empty-state">No pending decisions.</p>';
  }

  const resolvedSelectedDecisionId = selectedDecisionId ?? pendingDecisions[0].decision_id;
  const selectedDecision =
    pendingDecisions.find((decision) => decision.decision_id === resolvedSelectedDecisionId) ??
    pendingDecisions[0];
  const escapedSelectedTitle = escapeHtml(selectedDecision.title);
  const escapedSelectedPrompt = escapeHtml(selectedDecision.prompt);

  return `
    <div class="planner-decision-layout">
      <div class="planner-decision-list" role="list" aria-label="Pending decisions">
        ${pendingDecisions
          .map((decision) => {
            const escapedDecisionId = escapeAttribute(decision.decision_id);
            const escapedDecisionTitle = escapeHtml(decision.title);
            return `
              <button
                type="button"
                class="planner-decision-link${decision.decision_id === selectedDecision.decision_id ? " is-active" : ""}"
                data-planner-decision="${escapedDecisionId}"
                aria-pressed="${decision.decision_id === selectedDecision.decision_id}"
              >
                <strong>${escapedDecisionTitle}</strong>
                <span>${decision.choices.length} choices</span>
              </button>
            `;
          })
          .join("")}
      </div>
      <article class="planner-decision-card">
        <h4>${escapedSelectedTitle}</h4>
        <p>${escapedSelectedPrompt}</p>
        <div class="planner-chip-row" aria-label="Decision choices">
          ${selectedDecision.choices
            .map((choice) => {
              const escapedChoice = escapeHtml(choice);
              const escapedChoiceAttribute = escapeAttribute(choice);
              return `
                <button
                  type="button"
                  class="planner-feedback-action planner-feedback-action--structured"
                  data-planner-decision-answer="${escapeAttribute(selectedDecision.decision_id)}"
                  data-planner-decision-choice="${escapedChoiceAttribute}"
                >
                  ${escapedChoice}
                </button>
              `;
            })
            .join("")}
        </div>
      </article>
    </div>
  `;
}

/**
 * @param {PlannerPanelViewState} state
 * @returns {string}
 */
function renderPendingDecisions(state) {
  return renderPendingDecisionsComponent(
    state.data.pending_decisions,
    state.ui.selected_decision_id ?? state.data.pending_decisions[0]?.decision_id ?? null
  );
}

/**
 * @param {PlannerBehaviorRecord} behavior
 * @returns {{ feedback_kind: string, label: string }[]}
 */
function getFeedbackPromptActions(behavior) {
  return [
    {
      feedback_kind: "show_options_sooner",
      label: behavior.surface_options_early ? "Show options even sooner" : "Show options sooner",
    },
    {
      feedback_kind: "do_more_before_asking",
      label: behavior.target_research_passes > 2 ? "Do more before asking again" : "Research deeper first",
    },
    {
      feedback_kind: "ask_me_earlier",
      label: behavior.ask_before_next_major_change ? "Ask me earlier on route changes" : "Check in sooner",
    },
    {
      feedback_kind: "explain_more",
      label: behavior.explanation_density === "detailed" ? "Keep the detailed rationale" : "Explain more",
    },
    {
      feedback_kind: "explain_less",
      label: behavior.explanation_density === "lean" ? "Keep this concise" : "Explain less",
    },
  ];
}

/**
 * @param {OptionSetRecord} optionSet
 * @param {PlannerBehaviorRecord} behavior
 * @returns {string}
 */
export function renderOptionFeedbackPromptsComponent(optionSet, behavior) {
  if (!optionSet.options.length) {
    return '<p class="planner-empty-state">No option feedback prompts yet.</p>';
  }

  const feedbackActions = getFeedbackPromptActions(behavior);

  return `
    <div class="planner-feedback-layout" aria-label="Option feedback prompts">
      ${optionSet.options
        .map(
          (option) => `
            <article class="planner-feedback-card" data-planner-option-feedback="${option.option_id}">
              <div class="planner-section-header">
                <h4>${option.label}</h4>
                <span class="planner-meta">${option.kind}</span>
              </div>
              <p class="planner-feedback-summary">${option.summary}</p>
              <div class="planner-feedback-prompts">
                <label class="planner-feedback-field">
                  <span>What feels strongest about this option?</span>
                  <textarea
                    rows="3"
                    name="feedback-positive-${option.option_id}"
                    placeholder="Example: Keep the walkable core, but I need calmer nights."
                  ></textarea>
                </label>
                <label class="planner-feedback-field">
                  <span>What should the planner change if this misses?</span>
                  <textarea
                    rows="3"
                    name="feedback-revise-${option.option_id}"
                    placeholder="Example: Hold the same neighborhood access, but widen the room and arrival buffer."
                  ></textarea>
                </label>
              </div>
              <div class="planner-chip-row" aria-label="Feedback prompt suggestions">
                ${feedbackActions
                  .map(
                    (action) => `
                      <button
                        type="button"
                        class="planner-feedback-action"
                        data-planner-feedback-kind="${action.feedback_kind}"
                        data-planner-option-id="${option.option_id}"
                      >
                        ${action.label}
                      </button>
                    `
                  )
                  .join("")}
              </div>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

/**
 * @param {OptionSetRecord} optionSet
 * @param {string | null} selectedDecisionId
 * @returns {string}
 */
export function renderStructuredResponseCaptureComponent(optionSet, selectedDecisionId = null) {
  if (!optionSet.options.length) {
    return '<p class="planner-empty-state">No structured response actions available.</p>';
  }

  return `
    <div class="planner-feedback-layout" aria-label="Structured response capture actions">
      ${optionSet.options
        .map(
          (option) => `
            <article class="planner-feedback-card" data-planner-response-card="${option.option_id}">
              <div class="planner-section-header">
                <h4>${option.label}</h4>
                <span class="planner-meta">Structured response</span>
              </div>
              <p class="planner-feedback-summary">${option.summary}</p>
              <div class="planner-chip-row" aria-label="Structured response actions">
                ${[
                  ["accept", "Accept"],
                  ["reject", "Reject"],
                  ["revise", "Revise"],
                  ["save_as_fallback", "Save as fallback"],
                  ["do_more_before_asking_again", "Do more before asking again"],
                ]
                  .map(
                    ([actionKind, label]) => `
                      <button
                        type="button"
                        class="planner-feedback-action planner-feedback-action--structured"
                        data-planner-response-action="${actionKind}"
                        data-planner-option-id="${option.option_id}"
                        data-planner-decision-id="${selectedDecisionId ?? ""}"
                      >
                        ${label}
                      </button>
                    `
                  )
                  .join("")}
              </div>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

/**
 * @param {NextStepActionRecord[]} nextStepActions
 * @param {PlannerPanelSection} activeSection
 * @returns {string}
 */
export function renderNextStepActionsComponent(nextStepActions, activeSection) {
  if (!nextStepActions.length) {
    return '<p class="planner-empty-state">No next-step actions available.</p>';
  }

  return `
    <div class="planner-next-step-layout" role="list" aria-label="Next-step actions">
      ${nextStepActions
        .map(
          (action) => `
            <article
              class="planner-output-card planner-next-step-card planner-next-step-card--${action.emphasis}${action.target_section === activeSection ? " is-contextual" : ""}"
              role="listitem"
              data-planner-next-step="${action.action_id}"
              data-planner-action-kind="${action.action_kind}"
            >
              <div class="planner-section-header">
                <h4>${action.label}</h4>
                <span class="planner-meta">${formatSectionLabel(action.target_section)}</span>
              </div>
              <p>${action.description}</p>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

/**
 * @param {PolicyEvaluationRecord | null} policyEvaluation
 * @returns {string}
 */
export function renderPolicyPostureDisplayComponent(policyEvaluation) {
  if (!policyEvaluation) {
    return `
      <p class="planner-empty-state">
        Business approval-readiness is not active for this planner state.
      </p>
    `;
  }

  const statusLabel = policyEvaluation.status.replaceAll("_", " ");
  const scorePercent = Math.round(policyEvaluation.compliance_score * 100);
  const scoreTone =
    policyEvaluation.status === "compliant"
      ? "positive"
      : policyEvaluation.status === "exception_required"
        ? "caution"
        : "critical";
  const blockingFailures = policyEvaluation.failure_reasons.filter(
    (failure) => failure.severity === "blocking"
  ).length;

  return `
    <div class="planner-feedback-layout" aria-label="Policy posture display">
      <article class="planner-output-card" data-policy-status="${policyEvaluation.status}">
        <div class="planner-section-header">
          <h4>Policy posture</h4>
          <span class="planner-status-pill planner-status-pill--${scoreTone}">${statusLabel}</span>
        </div>
        <p>Compliance score: ${scorePercent}%</p>
        <div class="planner-chip-row" aria-label="Policy posture summary">
          <span class="planner-chip">${policyEvaluation.approval_requirements.length} approval requirement${policyEvaluation.approval_requirements.length === 1 ? "" : "s"}</span>
          <span class="planner-chip">${policyEvaluation.failure_reasons.length} policy issue${policyEvaluation.failure_reasons.length === 1 ? "" : "s"}</span>
          <span class="planner-chip">${blockingFailures} blocking</span>
        </div>
      </article>
      <article class="planner-output-card">
        <div class="planner-section-header">
          <h4>Approvals</h4>
          <span class="planner-meta">${policyEvaluation.approval_requirements.length} roles</span>
        </div>
        ${
          policyEvaluation.approval_requirements.length
            ? `
              <ul class="planner-list">
                ${policyEvaluation.approval_requirements
                  .map(
                    (requirement) => `
                      <li>
                        <strong>${requirement.role}</strong>: ${requirement.reason}
                        ${requirement.mandatory ? " Required." : " Optional."}
                      </li>
                    `
                  )
                  .join("")}
              </ul>
            `
            : '<p class="planner-empty-state">No approval roles required.</p>'
        }
      </article>
      <article class="planner-output-card">
        <div class="planner-section-header">
          <h4>Policy findings</h4>
          <span class="planner-meta">${policyEvaluation.failure_reasons.length} issues</span>
        </div>
        ${
          policyEvaluation.failure_reasons.length
            ? `
              <ul class="planner-list">
                ${policyEvaluation.failure_reasons
                  .map(
                    (failure) => `
                      <li>
                        <strong>${failure.related_category || failure.code}</strong>: ${failure.message}
                        (${failure.severity})
                      </li>
                    `
                  )
                  .join("")}
              </ul>
            `
            : '<p class="planner-empty-state">No policy failures identified.</p>'
        }
      </article>
      <article class="planner-output-card">
        <div class="planner-section-header">
          <h4>Preferred alternatives</h4>
          <span class="planner-meta">${policyEvaluation.preferred_alternatives.length} options</span>
        </div>
        ${
          policyEvaluation.preferred_alternatives.length
            ? `
              <ul class="planner-list">
                ${policyEvaluation.preferred_alternatives
                  .map(
                    (alternative) => `
                      <li>
                        <strong>${alternative.category}</strong>: ${alternative.summary}
                        ${alternative.rationale}
                      </li>
                    `
                  )
                  .join("")}
              </ul>
            `
            : '<p class="planner-empty-state">No preferred alternatives suggested.</p>'
        }
      </article>
      <article class="planner-output-card">
        <div class="planner-section-header">
          <h4>Exception guidance</h4>
          <span class="planner-meta">${policyEvaluation.exception_guidance.length} notes</span>
        </div>
        ${
          policyEvaluation.exception_guidance.length
            ? `
              <ul class="planner-list">
                ${policyEvaluation.exception_guidance.map((guidance) => `<li>${guidance}</li>`).join("")}
              </ul>
            `
            : '<p class="planner-empty-state">No exception guidance required.</p>'
        }
      </article>
      <article class="planner-output-card">
        <div class="planner-section-header">
          <h4>Policy notes</h4>
          <span class="planner-meta">${policyEvaluation.notes.length} updates</span>
        </div>
        ${
          policyEvaluation.notes.length
            ? `
              <ul class="planner-list">
                ${policyEvaluation.notes.map((note) => `<li>${note}</li>`).join("")}
              </ul>
            `
            : '<p class="planner-empty-state">No policy notes yet.</p>'
        }
      </article>
    </div>
  `;
}

/**
 * @param {ProposalRecord | null} proposal
 * @param {PolicyEvaluationRecord | null} policyEvaluation
 * @returns {string}
 */
export function renderComparablesDisplayComponent(proposal, policyEvaluation) {
  if (!proposal?.comparables.length) {
    return '<p class="planner-empty-state">No comparable options attached to this approval review.</p>';
  }

  const preferredRefs = new Set(
    (policyEvaluation?.preferred_alternatives ?? [])
      .map((alternative) => alternative.comparable_ref)
      .filter(Boolean)
  );

  return `
    <div class="planner-output-feed" role="list" aria-label="Comparable options">
      ${proposal.comparables
        .map((comparable) => {
          const amount = comparable.estimated_cost.typical_amount.toFixed(0);
          const isPreferredFallback = preferredRefs.has(comparable.category);

          return `
            <article
              class="planner-output-card"
              role="listitem"
              data-planner-comparable-category="${comparable.category}"
            >
              <div class="planner-section-header">
                <h4>${comparable.label}</h4>
                <span class="planner-meta">${comparable.category}</span>
              </div>
              <p>${comparable.vendor} via ${comparable.booking_channel}</p>
              <div class="planner-chip-row" aria-label="Comparable option details">
                <span class="planner-chip">${comparable.estimated_cost.currency} ${amount}</span>
                ${isPreferredFallback ? '<span class="planner-chip">Preferred fallback</span>' : ""}
              </div>
              ${
                comparable.notes.length
                  ? `
                    <ul class="planner-list">
                      ${comparable.notes.map((note) => `<li>${note}</li>`).join("")}
                    </ul>
                  `
                  : '<p class="planner-empty-state">No comparable notes recorded.</p>'
              }
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

/**
 * @param {ProposalRecord | null} proposal
 * @param {PolicyEvaluationRecord | null} policyEvaluation
 * @returns {string}
 */
export function renderJustificationBurdenComponent(proposal, policyEvaluation) {
  const justifications = proposal?.justifications ?? [];
  const approvalNotes = proposal?.approval_notes ?? [];
  const requestedException = proposal?.requested_exception ?? null;
  const approvalRequirements = policyEvaluation?.approval_requirements ?? [];
  const documentationCount =
    justifications.length +
    approvalNotes.length +
    (requestedException ? 1 : 0) +
    approvalRequirements.length;

  if (!documentationCount) {
    return '<p class="planner-empty-state">No justification burden is attached to this approval review.</p>';
  }

  return `
    <div class="planner-feedback-layout" aria-label="Justification burden">
      <article class="planner-output-card" data-justification-burden="summary">
        <div class="planner-section-header">
          <h4>Documentation burden</h4>
          <span class="planner-meta">${documentationCount} items</span>
        </div>
        <div class="planner-chip-row" aria-label="Documentation burden summary">
          <span class="planner-chip">${justifications.length} justification record${justifications.length === 1 ? "" : "s"}</span>
          <span class="planner-chip">${approvalRequirements.length} approval role${approvalRequirements.length === 1 ? "" : "s"}</span>
          <span class="planner-chip">${approvalNotes.length} approval note${approvalNotes.length === 1 ? "" : "s"}</span>
          ${requestedException ? '<span class="planner-chip">Exception request attached</span>' : ""}
        </div>
      </article>
      <article class="planner-output-card">
        <div class="planner-section-header">
          <h4>Justification records</h4>
          <span class="planner-meta">${justifications.length} attached</span>
        </div>
        ${
          justifications.length
            ? `
              <ul class="planner-list">
                ${justifications
                  .map(
                    (justification) => `
                      <li data-justification-category="${justification.category}">
                        <strong>${justification.category}</strong>: ${justification.summary}
                        ${
                          justification.evidence.length
                            ? ` Evidence: ${justification.evidence.join(" ")}`
                            : ""
                        }
                      </li>
                    `
                  )
                  .join("")}
              </ul>
            `
            : '<p class="planner-empty-state">No justification records attached.</p>'
        }
      </article>
      <article class="planner-output-card">
        <div class="planner-section-header">
          <h4>Approval packet notes</h4>
          <span class="planner-meta">${approvalNotes.length} notes</span>
        </div>
        ${
          approvalNotes.length
            ? `
              <ul class="planner-list">
                ${approvalNotes.map((note) => `<li>${note}</li>`).join("")}
              </ul>
            `
            : '<p class="planner-empty-state">No approval notes captured yet.</p>'
        }
      </article>
      <article class="planner-output-card">
        <div class="planner-section-header">
          <h4>Exception request</h4>
          <span class="planner-meta">${requestedException ? requestedException.exception_type.replaceAll("_", " ") : "not requested"}</span>
        </div>
        ${
          requestedException
            ? `
              <p>${requestedException.reason}</p>
              <div class="planner-chip-row" aria-label="Exception request approvals">
                ${requestedException.requested_approval_roles.map((role) => `<span class="planner-chip">${role}</span>`).join("")}
              </div>
              ${
                requestedException.notes.length
                  ? `
                    <ul class="planner-list">
                      ${requestedException.notes.map((note) => `<li>${note}</li>`).join("")}
                    </ul>
                  `
                  : '<p class="planner-empty-state">No exception notes captured yet.</p>'
              }
            `
            : '<p class="planner-empty-state">No exception request is required for this proposal.</p>'
        }
      </article>
    </div>
  `;
}

/**
 * @param {ProposalRecord | null} proposal
 * @param {PolicyEvaluationRecord | null} policyEvaluation
 * @returns {string}
 */
export function renderProposalReadinessIndicatorComponent(proposal, policyEvaluation) {
  if (!proposal || !policyEvaluation) {
    return '<p class="planner-empty-state">No proposal readiness state is available for this planner review.</p>';
  }

  const comparableCount = proposal.comparables.length;
  const justificationCount = proposal.justifications?.length ?? 0;
  const approvalRoleCount = policyEvaluation.approval_requirements.length;
  const blockingFailureCount = policyEvaluation.failure_reasons.filter(
    (failure) => failure.severity === "blocking"
  ).length;
  const hasExceptionPath = policyEvaluation.status !== "exception_required" || Boolean(proposal.requested_exception);
  const readinessChecks = [
    {
      label: "Comparables attached",
      detail: `${comparableCount} option${comparableCount === 1 ? "" : "s"} in the approval packet`,
      complete: comparableCount > 0,
    },
    {
      label: "Business rationale captured",
      detail: `${justificationCount} justification record${justificationCount === 1 ? "" : "s"}`,
      complete: justificationCount > 0,
    },
    {
      label: "Approval route identified",
      detail: `${approvalRoleCount} approver role${approvalRoleCount === 1 ? "" : "s"} identified`,
      complete: approvalRoleCount > 0 || policyEvaluation.status === "compliant",
    },
    {
      label: "Submission path defined",
      detail:
        policyEvaluation.status === "exception_required"
          ? hasExceptionPath
            ? "Exception request is attached"
            : "Exception request is still missing"
          : "No exception packet required",
      complete: hasExceptionPath,
    },
  ];
  const completedChecks = readinessChecks.filter((check) => check.complete).length;
  const readinessPercent = Math.round((completedChecks / readinessChecks.length) * 100);
  const statusTone =
    blockingFailureCount > 0
      ? "critical"
      : readinessPercent === 100
        ? "positive"
        : "caution";
  const readinessLabel =
    blockingFailureCount > 0
      ? "blocked"
      : readinessPercent === 100
        ? policyEvaluation.status === "exception_required"
          ? "exception packet ready"
          : "ready to submit"
        : "needs completion";
  const nextRequiredActions = [];
  if (blockingFailureCount > 0) {
    nextRequiredActions.push(
      ...policyEvaluation.failure_reasons
        .filter((failure) => failure.severity === "blocking")
        .map((failure) => failure.message)
        .filter((message) => typeof message === "string" && message.trim().length > 0)
    );
  }
  if (!hasExceptionPath && policyEvaluation.status === "exception_required") {
    nextRequiredActions.push("Attach an exception request with required approver roles.");
  }
  if (comparableCount === 0) {
    nextRequiredActions.push("Add at least one comparable option to the approval packet.");
  }
  if (justificationCount === 0) {
    nextRequiredActions.push("Add at least one business justification record.");
  }
  if (approvalRoleCount === 0 && policyEvaluation.status !== "compliant") {
    nextRequiredActions.push("Identify approver roles for the selected policy path.");
  }
  const dedupedNextActions = [...new Set(nextRequiredActions)];

  return `
    <div class="planner-feedback-layout" aria-label="Proposal readiness indicator">
      <article
        class="planner-output-card"
        data-proposal-readiness="${readinessLabel.replaceAll(" ", "-")}"
      >
        <div class="planner-section-header">
          <h4>Proposal readiness</h4>
          <span class="planner-status-pill planner-status-pill--${statusTone}">${readinessLabel}</span>
        </div>
        <p>${completedChecks} of ${readinessChecks.length} approval checks complete.</p>
        <div
          class="planner-readiness-meter"
          role="progressbar"
          aria-label="Proposal readiness progress"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow="${readinessPercent}"
        >
          <span class="planner-readiness-meter__fill planner-readiness-meter__fill--${statusTone}" style="width: ${readinessPercent}%"></span>
        </div>
        <div class="planner-chip-row" aria-label="Proposal readiness summary">
          <span class="planner-chip">${Math.round(policyEvaluation.compliance_score * 100)}% compliance</span>
          <span class="planner-chip">${blockingFailureCount} blocking issue${blockingFailureCount === 1 ? "" : "s"}</span>
          <span class="planner-chip">${approvalRoleCount} approver${approvalRoleCount === 1 ? "" : "s"}</span>
        </div>
      </article>
      <article class="planner-output-card">
        <div class="planner-section-header">
          <h4>Approval checklist</h4>
          <span class="planner-meta">${completedChecks}/${readinessChecks.length} complete</span>
        </div>
        <ul class="planner-list">
          ${readinessChecks
            .map(
              (check) => `
                <li data-readiness-complete="${check.complete}">
                  <strong>${check.complete ? "Ready" : "Open"}:</strong> ${check.label}. ${check.detail}.
                </li>
              `
            )
            .join("")}
        </ul>
      </article>
      <article class="planner-output-card">
        <div class="planner-section-header">
          <h4>Next required actions</h4>
          <span class="planner-meta">${dedupedNextActions.length} item${dedupedNextActions.length === 1 ? "" : "s"}</span>
        </div>
        ${
          dedupedNextActions.length
            ? `
              <ul class="planner-list" aria-label="Proposal next required actions">
                ${dedupedNextActions.map((action) => `<li data-proposal-next-action="required">${action}</li>`).join("")}
              </ul>
            `
            : '<p class="planner-empty-state">No additional actions are required before submission.</p>'
        }
      </article>
    </div>
  `;
}

/**
 * @param {PlannerPanelViewState} state
 * @returns {string}
 */
function renderPolicyStatus(state) {
  return `
    <section aria-label="Proposal readiness review">
      <div class="planner-section-header">
        <h3>Proposal Readiness</h3>
        <span class="planner-meta">${state.data.policy_evaluation ? "active" : "inactive"}</span>
      </div>
      ${renderProposalReadinessIndicatorComponent(state.data.proposal, state.data.policy_evaluation)}
    </section>
    ${renderPolicyPostureDisplayComponent(state.data.policy_evaluation)}
    <section aria-label="Justification burden review">
      <div class="planner-section-header">
        <h3>Justification Burden</h3>
        <span class="planner-meta">${state.data.proposal?.justifications?.length ?? 0} records</span>
      </div>
      ${renderJustificationBurdenComponent(state.data.proposal, state.data.policy_evaluation)}
    </section>
    <section aria-label="Comparables review">
      <div class="planner-section-header">
        <h3>Comparables</h3>
        <span class="planner-meta">${state.data.proposal?.comparables.length ?? 0} options</span>
      </div>
      ${renderComparablesDisplayComponent(state.data.proposal, state.data.policy_evaluation)}
    </section>
  `;
}

/**
 * @param {PlannerPanelViewState} state
 * @returns {string}
 */
function renderOptions(state) {
  const { option_set: optionSet } = state.data;
  const selectedDecisionId = state.ui.selected_decision_id ?? state.data.pending_decisions[0]?.decision_id ?? null;

  return `
    <div class="planner-output-card">
      <h4>${optionSet.title}</h4>
      <p>${optionSet.explanation[0] ?? "Planner comparison set ready."}</p>
      <div class="planner-chip-row">
        ${optionSet.comparison_axes.map((axis) => `<span class="planner-chip">${axis.label}</span>`).join("")}
      </div>
      <ul class="planner-list">
        ${optionSet.options.map((option) => `<li><strong>${option.label}</strong>: ${option.summary}</li>`).join("")}
      </ul>
    </div>
    ${renderOptionFeedbackPromptsComponent(optionSet, state.data.planner_behavior)}
    ${renderStructuredResponseCaptureComponent(optionSet, selectedDecisionId)}
  `;
}

/**
 * @param {PlannerPanelState} data
 * @param {StructuredResponseActionKind} actionType
 * @param {string} optionId
 * @param {string | null} decisionId
 * @returns {{ eventName: string, detail: Record<string, unknown> }}
 */
function createStructuredResponseEvent(data, actionType, optionId, decisionId) {
  /** @type {StructuredResponseBaseDetail} */
  const baseDetail = {
    action_type: actionType,
    trip_id: data.trip.trip_id,
    option_set_id: data.option_set.option_set_id,
    option_id: optionId,
    decision_id: decisionId,
    source_section: "options",
  };

  if (actionType === "accept") {
    return {
      eventName: "planner-response-accept",
      detail: {
        ...baseDetail,
        accepted_option_id: optionId,
      },
    };
  }

  if (actionType === "reject") {
    return {
      eventName: "planner-response-reject",
      detail: {
        ...baseDetail,
        rejected_option_id: optionId,
      },
    };
  }

  if (actionType === "revise") {
    return {
      eventName: "planner-response-revise",
      detail: {
        ...baseDetail,
        revision_target: {
          option_id: optionId,
          decision_id: decisionId,
        },
      },
    };
  }

  if (actionType === "save_as_fallback") {
    return {
      eventName: "planner-response-save-as-fallback",
      detail: {
        ...baseDetail,
        fallback_option_id: optionId,
      },
    };
  }

  return {
    eventName: "planner-response-do-more-before-asking-again",
    detail: {
      ...baseDetail,
      deferred_option_id: optionId,
      requested_follow_up: "do_more_before_asking_again",
    },
  };
}

/**
 * @param {PlannerPanelState} data
 * @param {string} decisionId
 * @param {string} choice
 * @returns {{ eventName: string, detail: Record<string, unknown> }}
 */
function createDecisionAnswerEvent(data, decisionId, choice) {
  return {
    eventName: "planner-decision-answer",
    detail: {
      trip_id: data.trip.trip_id,
      decision_id: decisionId,
      choice,
      source_section: "decisions",
    },
  };
}

/**
 * @param {PlannerPanelViewState} state
 * @returns {string}
 */
function renderActiveSectionMeta(state) {
  if (state.ui.active_section === "decisions") {
    return `${state.data.pending_decisions.length} waiting`;
  }

  if (state.ui.active_section === "options") {
    return state.data.option_set.scope;
  }

  if (state.ui.active_section === "approval") {
    return "Policy bridge";
  }

  return `${state.data.outputs.length} items`;
}

/**
 * @param {PlannerPanelViewState} state
 * @returns {string}
 */
function renderPlannerMarkup(state) {
  return `
    <section class="planner-shell" aria-label="Interactive planner workspace">
      <section class="planner-hero" aria-labelledby="planner-title">
        <p class="eyebrow">Interactive Planner</p>
        <h1 id="planner-title">${state.data.trip.title}</h1>
        <p>${state.data.trip.summary}</p>
        ${renderSummaryCards(state)}
      </section>
      <aside class="planner-panel" aria-label="Planner side panel">
        <header class="planner-panel-header">
          <div>
            <h2>Planner Side Panel</h2>
            <p>Structured orchestration output, ready for traveler interaction.</p>
          </div>
          <span class="planner-status-pill">${state.data.trip.status.replaceAll("_", " ")}</span>
        </header>
        ${renderBehaviorSummary(state.data.planner_behavior)}
        ${renderSectionTabs(state)}
        <div class="planner-sections">
          ${PANEL_SECTIONS.map(
            (section) => `
              <section
                class="planner-section"
                id="${getSectionPanelId(section)}"
                role="tabpanel"
                aria-labelledby="${getSectionTabId(section)}"
                ${state.ui.active_section === section ? "" : "hidden"}
              >
                <div class="planner-section-header">
                  <h3>${formatSectionLabel(section)}</h3>
                  <span class="planner-meta">${section === state.ui.active_section ? renderActiveSectionMeta(state) : ""}</span>
                </div>
                ${renderSectionContent(section, state)}
              </section>
            `
          ).join("")}
          <section class="planner-section" aria-labelledby="planner-next-step-title">
            <div class="planner-section-header">
              <h3 id="planner-next-step-title">Next-Step Actions</h3>
              <span class="planner-meta">${state.data.next_step_actions.length} ready</span>
            </div>
            ${renderNextStepActionsComponent(state.data.next_step_actions, state.ui.active_section)}
          </section>
        </div>
        <p class="planner-footer-note">
          The side panel now owns local UI state for active section focus and pending-decision selection.
        </p>
      </aside>
    </section>
  `;
}

/**
 * @param {PlannerPanelState} data
 * @returns {{
 *   getState: () => PlannerPanelViewState,
 *   setActiveSection: (section: PlannerPanelSection) => PlannerPanelViewState,
 *   selectDecision: (decisionId: string) => PlannerPanelViewState,
 *   replaceData: (nextData: PlannerPanelState) => PlannerPanelViewState
 * }}
 */
export function createPlannerSidePanelStore(data) {
  /** @type {PlannerPanelViewState} */
  let state = createInitialViewState(data);

  return {
    getState() {
      return state;
    },
    setActiveSection(section) {
      if (!PANEL_SECTIONS.includes(section)) {
        return state;
      }

      state = {
        ...state,
        ui: {
          ...state.ui,
          active_section: section,
        },
      };
      return state;
    },
    selectDecision(decisionId) {
      if (!state.data.pending_decisions.some((decision) => decision.decision_id === decisionId)) {
        return state;
      }

      state = {
        ...state,
        ui: {
          ...state.ui,
          active_section: "decisions",
          selected_decision_id: decisionId,
        },
      };
      return state;
    },
    replaceData(nextData) {
      const nextState = createInitialViewState(nextData);
      const selectedDecisionId = nextData.pending_decisions.some(
        (decision) => decision.decision_id === state.ui.selected_decision_id
      )
        ? state.ui.selected_decision_id
        : nextState.ui.selected_decision_id;

      state = {
        data: nextData,
        ui: {
          active_section: PANEL_SECTIONS.includes(state.ui.active_section)
            ? state.ui.active_section
            : nextState.ui.active_section,
          selected_decision_id: selectedDecisionId,
        },
      };
      return state;
    },
  };
}

/**
 * @typedef {{
 *   getState: () => PlannerPanelViewState,
 *   setActiveSection: (section: PlannerPanelSection) => PlannerPanelViewState,
 *   selectDecision: (decisionId: string) => PlannerPanelViewState,
 *   replaceState: (nextData: PlannerPanelState) => PlannerPanelViewState,
 *   destroy: () => void,
 * }} PlannerSidePanelController
 */

/**
 * @param {HTMLElement} mountNode
 * @param {PlannerPanelState} initialState
 * @returns {PlannerSidePanelController}
 */
export function renderPlannerSidePanel(mountNode, initialState) {
  const store = createPlannerSidePanelStore(initialState);

  function render() {
    mountNode.innerHTML = renderPlannerMarkup(store.getState());
  }

  /**
   * @param {Event} event
   */
  function handleClick(event) {
    const target = event.target;

    if (!(target instanceof Element)) {
      return;
    }

    const sectionButton = target.closest("[data-planner-section]");
    if (sectionButton instanceof HTMLElement) {
      store.setActiveSection(
        /** @type {PlannerPanelSection} */ (sectionButton.dataset.plannerSection ?? "outputs")
      );
      render();
      return;
    }

    const decisionButton = target.closest("[data-planner-decision]");
    if (decisionButton instanceof HTMLElement && decisionButton.dataset.plannerDecision) {
      store.selectDecision(decisionButton.dataset.plannerDecision);
      render();
      return;
    }

    const responseButton = target.closest("[data-planner-response-action]");
    if (
      responseButton instanceof HTMLElement &&
      responseButton.dataset.plannerResponseAction &&
      responseButton.dataset.plannerOptionId
    ) {
      const { eventName, detail } = createStructuredResponseEvent(
        store.getState().data,
        /** @type {StructuredResponseActionKind} */ (responseButton.dataset.plannerResponseAction),
        responseButton.dataset.plannerOptionId,
        responseButton.dataset.plannerDecisionId || null
      );

      mountNode.dispatchEvent(new CustomEvent(eventName, { detail }));
      return;
    }

    const decisionAnswerButton = target.closest("[data-planner-decision-answer]");
    if (
      decisionAnswerButton instanceof HTMLElement &&
      decisionAnswerButton.dataset.plannerDecisionAnswer &&
      decisionAnswerButton.dataset.plannerDecisionChoice
    ) {
      const { eventName, detail } = createDecisionAnswerEvent(
        store.getState().data,
        decisionAnswerButton.dataset.plannerDecisionAnswer,
        decisionAnswerButton.dataset.plannerDecisionChoice
      );
      mountNode.dispatchEvent(new CustomEvent(eventName, { detail }));
    }
  }

  /**
   * @param {KeyboardEvent} event
   */
  function handleKeydown(event) {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    const sectionButton = target.closest("[data-planner-section]");
    if (!(sectionButton instanceof HTMLElement) || !sectionButton.dataset.plannerSection) {
      return;
    }

    const currentSection = /** @type {PlannerPanelSection} */ (sectionButton.dataset.plannerSection);
    const currentIndex = PANEL_SECTIONS.indexOf(currentSection);
    if (currentIndex === -1) {
      return;
    }

    /** @type {PlannerPanelSection | null} */
    let nextSection = null;
    if (event.key === "ArrowRight") {
      nextSection = PANEL_SECTIONS[(currentIndex + 1) % PANEL_SECTIONS.length];
    } else if (event.key === "ArrowLeft") {
      nextSection = PANEL_SECTIONS[(currentIndex - 1 + PANEL_SECTIONS.length) % PANEL_SECTIONS.length];
    } else if (event.key === "Home") {
      nextSection = PANEL_SECTIONS[0];
    } else if (event.key === "End") {
      nextSection = PANEL_SECTIONS[PANEL_SECTIONS.length - 1];
    }

    if (nextSection) {
      event.preventDefault();
      store.setActiveSection(nextSection);
      render();
      const nextSectionButton = mountNode.querySelector(`[data-planner-section="${nextSection}"]`);
      if (nextSectionButton instanceof HTMLElement) {
        nextSectionButton.focus();
      }
    }
  }

  render();
  mountNode.addEventListener("click", handleClick);
  mountNode.addEventListener("keydown", handleKeydown);

  return {
    getState: store.getState,
    setActiveSection(section) {
      const nextState = store.setActiveSection(section);
      render();
      return nextState;
    },
    selectDecision(decisionId) {
      const nextState = store.selectDecision(decisionId);
      render();
      return nextState;
    },
    replaceState(nextData) {
      const nextState = store.replaceData(nextData);
      render();
      return nextState;
    },
    destroy() {
      mountNode.removeEventListener("click", handleClick);
      mountNode.removeEventListener("keydown", handleKeydown);
    },
  };
}
