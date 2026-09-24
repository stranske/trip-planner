/**
 * Route metrics as a traveller reads them.
 *
 * A connection count the planner did not measure arrives as null. It used to render as
 * "0", which told a traveller Seattle to Reykjavik was nonstop (issue 1839).
 */

export const NOT_MEASURED = "Not measured";

export function formatTransfers(count: number | null | undefined): string {
  if (count == null) {
    return NOT_MEASURED;
  }
  return `${count} transfer${count === 1 ? "" : "s"}`;
}

export function formatTransferDelta(delta: number | null | undefined): string {
  if (delta == null) {
    return NOT_MEASURED;
  }
  return `${delta >= 0 ? "+" : ""}${delta}`;
}

/** What a card may say about feasibility, given what was actually checked. */
export function describeAvailability(scenario: {
  feasible: boolean;
  availability_checked?: boolean;
}): string {
  if (!scenario.feasible) {
    return "Needs feasibility work";
  }
  return scenario.availability_checked === false
    ? "Availability not checked with a provider"
    : "No blocking issue found";
}
