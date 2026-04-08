import { useEffect, useState, type FormEvent } from "react";

import type {
  ActualSpendEventUpsertPayload,
  BudgetCategoryAllocation,
  BudgetPlanUpsertPayload,
  BudgetWorkspaceState,
} from "../../api/workspace";

type BudgetAllocationDraft = {
  category_key: string;
  label: string;
  planned_amount: string;
};

type BudgetFormState = {
  title: string;
  currency: string;
  scenarioTitle: string;
  summary: string;
  allocations: BudgetAllocationDraft[];
};

type SpendFormState = {
  category_key: string;
  amount: string;
  source_context: string;
  merchant_name: string;
};

function titleCaseCategory(categoryKey: string): string {
  return categoryKey
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatCurrency(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function getActiveScenario(budgetState: BudgetWorkspaceState) {
  const plan = budgetState.budget_plan;
  if (!plan) {
    return null;
  }
  return (
    plan.scenario_budgets.find(
      (scenario) => scenario.scenario_budget_id === plan.current_scenario_budget_id
    ) ??
    plan.scenario_budgets[0] ??
    null
  );
}

function buildAllocationDrafts(budgetState: BudgetWorkspaceState): BudgetAllocationDraft[] {
  const activeScenario = getActiveScenario(budgetState);
  const allocationMap = new Map<string, BudgetCategoryAllocation>();

  for (const allocation of activeScenario?.allocations ?? []) {
    allocationMap.set(allocation.category_key, allocation);
  }

  const orderedKeys = [
    ...budgetState.summary.category_summaries.map((item) => item.category_key),
    ...budgetState.summary.suggested_categories,
  ].filter((value, index, items) => items.indexOf(value) === index);

  return orderedKeys.map((categoryKey) => {
    const summary =
      budgetState.summary.category_summaries.find(
        (item) => item.category_key === categoryKey
      ) ?? null;
    const allocation = allocationMap.get(categoryKey);

    return {
      category_key: categoryKey,
      label: allocation?.label ?? summary?.label ?? titleCaseCategory(categoryKey),
      planned_amount:
        allocation?.planned_amount != null && allocation.planned_amount > 0
          ? allocation.planned_amount.toString()
          : "",
    };
  });
}

function buildBudgetFormState(budgetState: BudgetWorkspaceState, tripMode: string): BudgetFormState {
  const plan = budgetState.budget_plan;
  const activeScenario = getActiveScenario(budgetState);

  return {
    title: plan?.title ?? `${titleCaseCategory(tripMode)} trip budget`,
    currency: plan?.currency ?? budgetState.summary.currency ?? "USD",
    scenarioTitle: activeScenario?.title ?? "Current working budget",
    summary:
      budgetState.versions[0]?.summary ??
      (plan ? "Updated workspace budget" : "Initial workspace budget"),
    allocations: buildAllocationDrafts(budgetState),
  };
}

function buildSpendFormState(budgetState: BudgetWorkspaceState): SpendFormState {
  return {
    category_key:
      budgetState.summary.category_summaries[0]?.category_key ??
      budgetState.summary.suggested_categories[0] ??
      "lodging",
    amount: "",
    source_context: "",
    merchant_name: "",
  };
}

export function WorkspaceBudgetPanel({
  budgetState,
  tripMode,
  busyLabel,
  errorMessage,
  onSaveBudget,
  onRecordSpend,
}: {
  budgetState: BudgetWorkspaceState;
  tripMode: string;
  busyLabel: string | null;
  errorMessage: string | null;
  onSaveBudget: (payload: BudgetPlanUpsertPayload) => Promise<void>;
  onRecordSpend: (payload: ActualSpendEventUpsertPayload) => Promise<void>;
}) {
  const [budgetForm, setBudgetForm] = useState<BudgetFormState>(() =>
    buildBudgetFormState(budgetState, tripMode)
  );
  const [spendForm, setSpendForm] = useState<SpendFormState>(() =>
    buildSpendFormState(budgetState)
  );
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const activeScenario = getActiveScenario(budgetState);

  useEffect(() => {
    setBudgetForm(buildBudgetFormState(budgetState, tripMode));
    setSpendForm(buildSpendFormState(budgetState));
    setValidationMessage(null);
  }, [budgetState, tripMode]);

  async function handleBudgetSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationMessage(null);

    const allocations = budgetForm.allocations
      .map((item) => ({
        category_key: item.category_key,
        label: item.label,
        planned_amount: Number(item.planned_amount),
        currency: budgetForm.currency,
        flexibility:
          budgetState.summary.category_summaries.find(
            (summary) => summary.category_key === item.category_key
          )?.flexibility ?? "flexible",
        notes: [] as string[],
      }))
      .filter((item) => Number.isFinite(item.planned_amount) && item.planned_amount > 0);

    if (allocations.length === 0) {
      setValidationMessage("Add at least one positive category cap before saving the budget.");
      return;
    }

    await onSaveBudget({
      title: budgetForm.title.trim(),
      currency: budgetForm.currency.trim().toUpperCase(),
      current_scenario_budget_id: activeScenario?.scenario_budget_id ?? null,
      tags: budgetState.budget_plan?.tags ?? [],
      notes: budgetState.budget_plan?.notes ?? [],
      scenario_budgets: [
        {
          scenario_budget_id: activeScenario?.scenario_budget_id ?? null,
          saved_scenario_id: activeScenario?.saved_scenario_id ?? null,
          title: budgetForm.scenarioTitle.trim(),
          summary: "",
          tags: activeScenario?.tags ?? [],
          notes: activeScenario?.notes ?? [],
          allocations,
        },
      ],
      summary: budgetForm.summary.trim(),
    });
  }

  async function handleSpendSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationMessage(null);

    const amount = Number(spendForm.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setValidationMessage("Spend amount must be greater than zero.");
      return;
    }
    if (spendForm.source_context.trim().length === 0) {
      setValidationMessage("Add a short spend context so the event can be understood later.");
      return;
    }

    await onRecordSpend({
      category_key: spendForm.category_key,
      amount,
      currency: budgetForm.currency.trim().toUpperCase(),
      source_kind: "manual",
      source_context: spendForm.source_context.trim(),
      scenario_budget_id: budgetState.summary.current_scenario_budget_id,
      merchant_name: spendForm.merchant_name.trim(),
      notes: [],
    });
  }

  return (
    <section className="status-card budget-panel-card">
      <p className="status-label">Budget state</p>
      <h2>Budget vs actual</h2>
      <p className="muted-copy">
        Planned caps, actual spend drift, and remaining category headroom should feed later planner tradeoff
        reasoning and in-trip replans.
      </p>
      {busyLabel ? <p className="muted-copy">{busyLabel}</p> : null}
      {errorMessage ? <p className="planner-inline-error">{errorMessage}</p> : null}
      {validationMessage ? <p className="planner-inline-error">{validationMessage}</p> : null}

      <dl className="budget-summary-grid">
        <div>
          <dt>Planned total</dt>
          <dd>{formatCurrency(budgetState.summary.planned_total, budgetState.summary.currency)}</dd>
        </div>
        <div>
          <dt>Actual total</dt>
          <dd>{formatCurrency(budgetState.summary.actual_total, budgetState.summary.currency)}</dd>
        </div>
        <div>
          <dt>Remaining</dt>
          <dd>{formatCurrency(budgetState.summary.remaining_total, budgetState.summary.currency)}</dd>
        </div>
        <div>
          <dt>Spend events</dt>
          <dd>{budgetState.summary.spend_event_count}</dd>
        </div>
      </dl>

      <div className="budget-layout">
        <form className="budget-form" onSubmit={handleBudgetSubmit}>
          <div className="budget-form-header">
            <label className="budget-field">
              <span>Budget title</span>
              <input
                aria-label="Budget title"
                value={budgetForm.title}
                onChange={(event) =>
                  setBudgetForm((current) => ({ ...current, title: event.target.value }))
                }
              />
            </label>

            <label className="budget-field">
              <span>Currency</span>
              <input
                aria-label="Currency"
                maxLength={3}
                value={budgetForm.currency}
                onChange={(event) =>
                  setBudgetForm((current) => ({ ...current, currency: event.target.value.toUpperCase() }))
                }
              />
            </label>
          </div>

          <label className="budget-field">
            <span>Scenario label</span>
            <input
              aria-label="Scenario label"
              value={budgetForm.scenarioTitle}
              onChange={(event) =>
                setBudgetForm((current) => ({ ...current, scenarioTitle: event.target.value }))
              }
            />
          </label>

          <label className="budget-field">
            <span>Update summary</span>
            <input
              aria-label="Update summary"
              value={budgetForm.summary}
              onChange={(event) =>
                setBudgetForm((current) => ({ ...current, summary: event.target.value }))
              }
            />
          </label>

          <div className="budget-allocation-grid">
            {budgetForm.allocations.map((allocation) => (
              <label key={allocation.category_key} className="budget-field">
                <span>{allocation.label} cap</span>
                <input
                  aria-label={`${allocation.label} cap`}
                  inputMode="decimal"
                  type="number"
                  min="0"
                  step="0.01"
                  value={allocation.planned_amount}
                  onChange={(event) =>
                    setBudgetForm((current) => ({
                      ...current,
                      allocations: current.allocations.map((item) =>
                        item.category_key === allocation.category_key
                          ? { ...item, planned_amount: event.target.value }
                          : item
                      ),
                    }))
                  }
                />
              </label>
            ))}
          </div>

          <button className="budget-action-button" disabled={busyLabel !== null} type="submit">
            Save budget plan
          </button>
        </form>

        <form className="budget-form" onSubmit={handleSpendSubmit}>
          <label className="budget-field">
            <span>Spend category</span>
            <select
              aria-label="Spend category"
              value={spendForm.category_key}
              onChange={(event) =>
                setSpendForm((current) => ({ ...current, category_key: event.target.value }))
              }
            >
              {budgetState.summary.category_summaries.map((summary) => (
                <option key={summary.category_key} value={summary.category_key}>
                  {summary.label}
                </option>
              ))}
            </select>
          </label>

          <label className="budget-field">
            <span>Amount</span>
            <input
              aria-label="Amount"
              inputMode="decimal"
              type="number"
              min="0"
              step="0.01"
              value={spendForm.amount}
              onChange={(event) =>
                setSpendForm((current) => ({ ...current, amount: event.target.value }))
              }
            />
          </label>

          <label className="budget-field">
            <span>Spend context</span>
            <input
              aria-label="Spend context"
              value={spendForm.source_context}
              onChange={(event) =>
                setSpendForm((current) => ({ ...current, source_context: event.target.value }))
              }
            />
          </label>

          <label className="budget-field">
            <span>Merchant</span>
            <input
              aria-label="Merchant"
              value={spendForm.merchant_name}
              onChange={(event) =>
                setSpendForm((current) => ({ ...current, merchant_name: event.target.value }))
              }
            />
          </label>

          <button className="budget-action-button" disabled={busyLabel !== null} type="submit">
            Record spend event
          </button>
        </form>
      </div>

      <div className="budget-category-list">
        {budgetState.summary.category_summaries.map((summary) => (
          <article key={summary.category_key} className="budget-category-row">
            <div>
              <h3>{summary.label}</h3>
              <p className="muted-copy">{summary.flexibility.replace("_", " ")}</p>
            </div>
            <dl>
              <div>
                <dt>Plan</dt>
                <dd>{formatCurrency(summary.planned_amount, summary.currency)}</dd>
              </div>
              <div>
                <dt>Actual</dt>
                <dd>{formatCurrency(summary.actual_amount, summary.currency)}</dd>
              </div>
              <div>
                <dt>Remaining</dt>
                <dd>{formatCurrency(summary.remaining_amount, summary.currency)}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>

      <div className="decision-stack">
        {budgetState.spend_events.length === 0 ? (
          <p className="muted-copy">No actual spend has been recorded yet for this trip.</p>
        ) : (
          budgetState.spend_events.slice(0, 4).map((event) => (
            <article key={event.spend_event_id} className="decision-card">
              <h3>{event.source_context}</h3>
              <p>
                {formatCurrency(event.amount, event.currency)} in {titleCaseCategory(event.category_key)}
              </p>
              <p>{event.merchant_name || "Manual entry"}</p>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
