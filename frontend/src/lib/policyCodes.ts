/**
 * What each Travel-Plan-Permission rule code means for the traveller.
 *
 * The first sentence of each entry is TPP's own failure message, taken from the rule that
 * emits the code (travel_plan_permission/policy.py and config/validation.yaml), so this
 * file restates TPP rather than inventing a policy. The second says what the traveller can
 * do about it here. Codes this file does not know are shown as-is: an unexplained code is
 * better than a guessed explanation.
 *
 * The planner chat explains the same codes from trip_planner/app/services/policy_codes.py;
 * tests/app/test_policy_code_parity.py fails if the two drift.
 */

export type PolicyCodeExplanation = {
  code: string;
  meaning: string;
  whatToDo: string | null;
};

const EXPLANATIONS: Record<string, { meaning: string; whatToDo: string }> = {
  fare_comparison: {
    meaning: "Fare comparison requires selected and lowest fare data.",
    whatToDo:
      "Enter the lowest fare you found for the same journey next to your flight price on the Budget tab, then submit again.",
  },
  fare_evidence: {
    meaning: "Screenshot or fare evidence must be attached to the request.",
    whatToDo:
      "Tick the fare-evidence box on the Budget tab once you hold a screenshot or quote, and give it to your approver with the packet.",
  },
  non_reimbursable: {
    meaning: "Expense details are required to check non-reimbursable items.",
    whatToDo: "List each expense on the Budget tab so it can be checked line by line.",
  },
  "BUD-001": {
    meaning: "The trip total is over the travel policy's spending limit.",
    whatToDo: "Reduce the costs on the Budget tab, or ask your approver for an exception.",
  },
};

/**
 * `tppMessage`, when the verdict carried one, always wins over the text above: it is what
 * the policy service actually said about this trip.
 */
export function explainPolicyCode(code: string, tppMessage?: string): PolicyCodeExplanation {
  const known = EXPLANATIONS[code];
  return {
    code,
    meaning: tppMessage?.trim() || known?.meaning || code,
    whatToDo: known?.whatToDo ?? null,
  };
}
