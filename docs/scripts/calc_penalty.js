// Soft Cost Penalty helper
// segmentCost: 1 (budget) | 2 (mid) | 3 (premium)
// globalSignificance: 1‑5  | CS: 0‑1
export function calcPenalty(segmentCost, globalSignificance, CS) {
  const COST_WEIGHT = 0.5;
  if (globalSignificance >= 4) return 0; // world‑class safeguard
  if (CS === 0) return 0;                // cost ignored
  return COST_WEIGHT * (segmentCost - 1) * CS * (1 - globalSignificance / 5);
}
