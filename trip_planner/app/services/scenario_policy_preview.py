"""Per-scenario policy preview for Compare surfaces (UX-only, non-authoritative)."""

from __future__ import annotations

from typing import Any

POLICY_PREVIEW_DISCLAIMER = (
    "Policy preview only — not the final TPP verdict."
)


def _money_amount(estimated_total: Any) -> tuple[float, str] | None:
    if not isinstance(estimated_total, dict):
        return None
    amount = estimated_total.get("typical_amount")
    currency = estimated_total.get("currency") or "USD"
    if not isinstance(amount, (int, float)):
        return None
    return float(amount), str(currency)


def _constraint_rules(policy_state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(policy_state, dict):
        return {}
    constraint_set = policy_state.get("constraint_set")
    return constraint_set if isinstance(constraint_set, dict) else {}


def build_scenario_policy_preview(
    *,
    policy_state: dict[str, Any] | None,
    trip_mode: str,
    duration_days: int | None,
    estimated_total: Any,
    unresolved_tradeoffs: list[dict[str, Any]] | None = None,
    scenario_notes: list[str] | None = None,
) -> dict[str, Any]:
    """Return a serializable, non-authoritative policy preview for one Compare scenario."""
    base = {
        "authoritative": False,
        "disclaimer": POLICY_PREVIEW_DISCLAIMER,
        "violations": [],
    }
    if trip_mode != "business":
        return {
            **base,
            "status": "not_applicable",
            "status_label": "Not applicable",
            "compliant": None,
            "snapshot_available": False,
        }

    constraint_set = _constraint_rules(policy_state)
    if not constraint_set:
        return {
            **base,
            "status": "preview_unavailable",
            "status_label": "No policy snapshot available",
            "compliant": None,
            "snapshot_available": False,
        }

    money = _money_amount(estimated_total)
    violations: list[dict[str, Any]] = []
    notes = [str(item) for item in (scenario_notes or []) if isinstance(item, str)]

    budget_rules = constraint_set.get("budget_rules")
    if isinstance(budget_rules, dict):
        cap_amount = budget_rules.get("max_trip_total_usd")
        rule_id = str(budget_rules.get("rule_id") or "BUD-001")
        if isinstance(cap_amount, (int, float)) and money is not None:
            actual_amount, currency = money
            if actual_amount > float(cap_amount):
                violations.append(
                    {
                        "rule_id": rule_id,
                        "message": (
                            f"Estimated trip total exceeds the configured spend cap "
                            f"({rule_id})."
                        ),
                        "cap_amount": float(cap_amount),
                        "actual_amount": actual_amount,
                        "currency": currency,
                    }
                )

    lodging_rules = constraint_set.get("lodging_rules")
    if isinstance(lodging_rules, dict):
        nightly_cap = lodging_rules.get("max_nightly_rate_usd")
        rule_id = str(lodging_rules.get("rule_id") or "LOD-001")
        nightly_actual = None
        if isinstance(estimated_total, dict):
            nightly_actual = estimated_total.get("nightly_typical_amount")
        if isinstance(nightly_cap, (int, float)) and isinstance(nightly_actual, (int, float)):
            currency = str(estimated_total.get("currency") or "USD") if isinstance(estimated_total, dict) else "USD"
            if float(nightly_actual) > float(nightly_cap):
                violations.append(
                    {
                        "rule_id": rule_id,
                        "message": (
                            f"Selected nightly rate exceeds the configured lodging cap ({rule_id})."
                        ),
                        "cap_amount": float(nightly_cap),
                        "actual_amount": float(nightly_actual),
                        "currency": currency,
                    }
                )

    for tradeoff in unresolved_tradeoffs or []:
        if not isinstance(tradeoff, dict):
            continue
        code = str(tradeoff.get("code") or "").lower()
        blocking = bool(tradeoff.get("blocking"))
        if code == "policy_exception_path" or (
            blocking and "policy" in str(tradeoff.get("summary") or "").lower()
        ):
            violations.append(
                {
                    "rule_id": "POL-EXC",
                    "message": str(
                        tradeoff.get("summary")
                        or "Scenario requires a policy exception before booking."
                    ),
                    "cap_amount": None,
                    "actual_amount": None,
                    "currency": None,
                }
            )

    if "exception-nearest" in notes and not any(
        item["rule_id"] == "POL-EXC" for item in violations
    ):
        violations.append(
            {
                "rule_id": "POL-EXC",
                "message": "Exception-nearest route requires approval before booking.",
                "cap_amount": None,
                "actual_amount": None,
                "currency": None,
            }
        )

    compliant = len(violations) == 0
    if compliant:
        status_label = "In policy (preview)"
    else:
        status_label = "Policy issues (preview)"

    return {
        **base,
        "status": "compliant" if compliant else "non_compliant",
        "status_label": status_label,
        "compliant": compliant,
        "snapshot_available": True,
        "violations": violations,
    }
