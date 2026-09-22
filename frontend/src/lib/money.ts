/**
 * Rendering money that may not exist.
 *
 * A money envelope arrives with its amount absent whenever no source has quoted that
 * component — which, until a provider adapter or a human override supplies one, is the
 * normal case rather than an error. `Intl.NumberFormat.format(null)` renders "$0", so a
 * render site that guards only the envelope prints a cost of zero for a trip nobody
 * priced. That is the failure this module exists to make hard: an approver can act on
 * "$0" and cannot act on "Not priced".
 */

export type MoneyAmount = {
  currency: string;
  typical_amount: number | null;
};

/** The label every surface uses for a component no source has quoted. */
export const NOT_PRICED = "Not priced";

/** The amount, or null when nothing quoted it. Never coerces an absent amount to zero. */
export function pricedAmount(money: MoneyAmount | null | undefined): number | null {
  if (money == null) {
    return null;
  }
  const amount = money.typical_amount;
  return typeof amount === "number" && Number.isFinite(amount) ? amount : null;
}

export function formatMoney(
  money: MoneyAmount | null | undefined,
  { fallback = NOT_PRICED }: { fallback?: string } = {}
): string {
  const amount = pricedAmount(money);
  if (amount == null || money == null) {
    return fallback;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: money.currency,
    maximumFractionDigits: 0,
  }).format(amount);
}
