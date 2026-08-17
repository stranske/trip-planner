import type { ScenarioPolicyPreview } from "../../api/workspace";
import { formatCurrency } from "../../lib/formatCurrency";

export const POLICY_PREVIEW_DISCLAIMER =
  "Policy preview only — not the final TPP verdict.";

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
    return `${preview.status_label}: ${primaryViolation.rule_id} cap ${formatCurrency(
      primaryViolation.cap_amount,
      primaryViolation.currency
    )} vs ${formatCurrency(primaryViolation.actual_amount, primaryViolation.currency)}`;
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
      return `${violation.rule_id}: ${formatCurrency(
        violation.cap_amount,
        violation.currency
      )} cap vs ${formatCurrency(violation.actual_amount, violation.currency)} selected`;
    }
    return `${violation.rule_id}: ${violation.message}`;
  });
}
