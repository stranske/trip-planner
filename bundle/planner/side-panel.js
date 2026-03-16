/**
 * @import { PlannerPanelState } from "./mock-state.js"
 */

function renderSummaryCards(trip) {
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

function renderOutputs(outputs) {
  if (!outputs.length) {
    return '<p class="planner-empty-state">No planner outputs yet.</p>';
  }

  return outputs
    .map(
      (output) => `
        <article class="planner-output-card">
          <h4>${output.title}</h4>
          <p>${output.body}</p>
          <div class="planner-chip-row">
            ${output.tags.map((tag) => `<span class="planner-chip">${tag}</span>`).join("")}
          </div>
        </article>
      `
    )
    .join("");
}

function renderPendingDecisions(pendingDecisions) {
  if (!pendingDecisions.length) {
    return '<p class="planner-empty-state">No pending decisions.</p>';
  }

  return pendingDecisions
    .map(
      (decision) => `
        <article class="planner-decision-card">
          <h4>${decision.title}</h4>
          <p>${decision.prompt}</p>
          <ul class="planner-option-list">
            ${decision.choices.map((choice) => `<li>${choice}</li>`).join("")}
          </ul>
        </article>
      `
    )
    .join("");
}

function renderPolicyStatus(policyEvaluation) {
  if (!policyEvaluation) {
    return `
      <p class="planner-empty-state">
        Business approval-readiness is not active for this leisure planner state.
      </p>
    `;
  }

  return `
    <div class="planner-output-card">
      <h4>${policyEvaluation.status.replaceAll("_", " ")}</h4>
      <p>Compliance score: ${Math.round(policyEvaluation.compliance_score * 100)}%</p>
      <ul class="planner-list">
        ${policyEvaluation.notes.map((note) => `<li>${note}</li>`).join("")}
      </ul>
    </div>
  `;
}

function renderOptions(optionSet) {
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
  `;
}

/**
 * @param {HTMLElement} mountNode
 * @param {PlannerPanelState} state
 */
export function renderPlannerSidePanel(mountNode, state) {
  mountNode.innerHTML = `
    <section class="planner-shell" aria-label="Interactive planner workspace">
      <section class="planner-hero" aria-labelledby="planner-title">
        <p class="eyebrow">Interactive Planner</p>
        <h1 id="planner-title">${state.trip.title}</h1>
        <p>${state.trip.summary}</p>
        ${renderSummaryCards(state.trip)}
      </section>
      <aside class="planner-panel" aria-label="Planner side panel">
        <header class="planner-panel-header">
          <div>
            <h2>Planner Side Panel</h2>
            <p>Structured orchestration output, ready for traveler interaction.</p>
          </div>
          <span class="planner-status-pill">${state.trip.status.replaceAll("_", " ")}</span>
        </header>
        <div class="planner-sections">
          <section class="planner-section" aria-labelledby="planner-outputs-title">
            <div class="planner-section-header">
              <h3 id="planner-outputs-title">Outputs</h3>
              <span class="planner-meta">${state.outputs.length} items</span>
            </div>
            ${renderOutputs(state.outputs)}
          </section>
          <section class="planner-section" aria-labelledby="planner-decisions-title">
            <div class="planner-section-header">
              <h3 id="planner-decisions-title">Pending Decisions</h3>
              <span class="planner-meta">${state.pending_decisions.length} waiting</span>
            </div>
            ${renderPendingDecisions(state.pending_decisions)}
          </section>
          <section class="planner-section" aria-labelledby="planner-options-title">
            <div class="planner-section-header">
              <h3 id="planner-options-title">Option Set</h3>
              <span class="planner-meta">${state.option_set.scope}</span>
            </div>
            ${renderOptions(state.option_set)}
          </section>
          <section class="planner-section" aria-labelledby="planner-policy-title">
            <div class="planner-section-header">
              <h3 id="planner-policy-title">Approval Readiness</h3>
              <span class="planner-meta">Policy bridge</span>
            </div>
            ${renderPolicyStatus(state.policy_evaluation)}
          </section>
        </div>
        <p class="planner-footer-note">
          This container establishes the layout for later state actions, approval components, and feedback prompts.
        </p>
      </aside>
    </section>
  `;
}
