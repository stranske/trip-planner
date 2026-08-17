import type { ScenarioPolicyPreview } from "../../api/workspace";

function formatMoney(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(amount);
  }
}

export function formatScenarioPolicyPreview(
  preview: ScenarioPolicyPreview | undefined
): string {
  if (preview == null) {
    return "No policy snapshot available";
  }
  if (!preview.snapshot_available) {
    return preview.status_label;
  }

  if (preview.compliant) {
    return preview.status_label;
  }

  const primaryViolation = preview.violations[0];
  if (primaryViolation == null) {
    return preview.status_label;
  }

  if (
    primaryViolation.cap_amount != null &&
    primaryViolation.actual_amount != null &&
    primaryViolation.currency
  ) {
    return `${preview.status_label}: ${primaryViolation.rule_id} cap ${formatMoney(
      primaryViolation.cap_amount,
      primaryViolation.currency
    )} vs ${formatMoney(primaryViolation.actual_amount, primaryViolation.currency)}`;
  }

  return `${preview.status_label}: ${primaryViolation.rule_id} — ${primaryViolation.message}`;
}

export function formatScenarioPolicyViolations(
  preview: ScenarioPolicyPreview | undefined
): string[] {
  if (preview == null || !preview.snapshot_available) {
    return [];
  }
  return preview.violations.map((violation) => {
    if (
      violation.cap_amount != null &&
      violation.actual_amount != null &&
      violation.currency
    ) {
      return `${violation.rule_id}: ${formatMoney(
        violation.cap_amount,
        violation.currency
      )} cap vs ${formatMoney(violation.actual_amount, violation.currency)} selected`;
    }
    return `${violation.rule_id}: ${violation.message}`;
  });
}
