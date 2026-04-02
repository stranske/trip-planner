# Budget Persistence Boundary

Issue `#541` adds the durable budget slice that hangs off the persisted trip container from issue `#539`.

## Intent

`BudgetPlan` stores the canonical pre-trip budget baseline and any scenario-specific variants without embedding the entire trip record.

`ActualSpendEvent` stores in-trip or post-trip spend observations with:

- budget category
- timestamp
- amount and currency
- source kind and freeform source context
- optional links back to saved-scenario ids and scenario-budget variants

## Relationship To Trips And Scenarios

The persisted trip record should keep only `budget_state_id` references. The budget state owns:

- per-category planned allocations
- multiple scenario-linked budget variants for the same trip
- actual spend events that can be filtered by trip, budget plan, scenario, or category

This keeps the boundary clean:

- trip identity and lifecycle stay in `PersistedTripRecord`
- saved-scenario history can evolve independently in issue `#540`
- budget replanning can switch `current_scenario_budget_id` without mutating trip identity
- later comparison and in-trip adjustment flows can reconcile planned-vs-actual spend from stable records

## Mode Distinction

Budget persistence keeps leisure and business plans distinct:

- leisure plans can use traveler-facing categories such as lodging, food, activities, and contingency
- business plans can additionally carry policy-sensitive categories such as workspace and client hospitality

That separation prevents later reimbursement or policy logic from flattening all spend into one undifferentiated cost blob.
