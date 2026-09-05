"""Per-scenario policy preview for Compare surfaces (UX-only, non-authoritative)."""

from __future__ import annotations

import math
from typing import Any

POLICY_PREVIEW_DISCLAIMER = "Policy preview only — not the final TPP verdict."


def _money_amount(estimated_total: Any) -> tuple[float, str] | None:
    if not isinstance(estimated_total, dict):
        return None
    amount = estimated_total.get("typical_amount")
    currency = estimated_total.get("currency") or "USD"
    if (
        isinstance(amount, bool)
        or not isinstance(amount, (int, float))
        or not math.isfinite(amount)
    ):
        return None
    return float(amount), str(currency)


def _constraint_rules(policy_state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(policy_state, dict):
        return {}
    constraint_set = policy_state.get("constraint_set")
    return constraint_set if isinstance(constraint_set, dict) else {}


def _preview_base() -> dict[str, Any]:
    return {
        "authoritative": False,
        "disclaimer": POLICY_PREVIEW_DISCLAIMER,
        "violations": [],
    }


def _budget_violations(
    budget_rules: dict[str, Any],
    money: tuple[float, str] | None,
    *,
    currency_hint: str = "USD",
) -> list[dict[str, Any]]:
    cap_amount = budget_rules.get("max_trip_total_usd")
    rule_id = str(budget_rules.get("rule_id") or "BUD-001")
    if (
        isinstance(cap_amount, bool)
        or not isinstance(cap_amount, (int, float))
        or not math.isfinite(cap_amount)
    ):
        return []
    currency = money[1] if money is not None else currency_hint
    if currency != "USD":
        return []
    if money is None:
        return [
            {
                "rule_id": rule_id,
                "message": "Trip cost is unavailable; the configured spend cap cannot be checked.",
                "cap_amount": float(cap_amount),
                "actual_amount": None,
                "currency": currency,
                "incomplete": True,
            }
        ]
    actual_amount, currency = money
    if actual_amount <= float(cap_amount):
        return []
    return [
        {
            "rule_id": rule_id,
            "message": (f"Estimated trip total exceeds the configured spend cap ({rule_id})."),
            "cap_amount": float(cap_amount),
            "actual_amount": actual_amount,
            "currency": currency,
        }
    ]


def _lodging_violations(
    lodging_rules: dict[str, Any],
    estimated_total: Any,
) -> list[dict[str, Any]]:
    nightly_cap = lodging_rules.get("max_nightly_rate_usd")
    rule_id = str(lodging_rules.get("rule_id") or "LOD-001")
    nightly_actual = None
    if isinstance(estimated_total, dict):
        nightly_actual = estimated_total.get("nightly_typical_amount")
    if not isinstance(nightly_cap, (int, float)) or not isinstance(nightly_actual, (int, float)):
        return []
    currency = (
        str(estimated_total.get("currency") or "USD")
        if isinstance(estimated_total, dict)
        else "USD"
    )
    if currency != "USD":
        return []
    if float(nightly_actual) <= float(nightly_cap):
        return []
    return [
        {
            "rule_id": rule_id,
            "message": (f"Selected nightly rate exceeds the configured lodging cap ({rule_id})."),
            "cap_amount": float(nightly_cap),
            "actual_amount": float(nightly_actual),
            "currency": currency,
        }
    ]


def _tradeoff_violations(unresolved_tradeoffs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for tradeoff in unresolved_tradeoffs or []:
        if not isinstance(tradeoff, dict):
            continue
        code = str(tradeoff.get("code") or "").lower()
        blocking = bool(tradeoff.get("blocking"))
        if code != "policy_exception_path" and not (
            blocking and "policy" in str(tradeoff.get("summary") or "").lower()
        ):
            continue
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
    return violations


def _exception_note_violation(
    notes: list[str],
    violations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if "exception-nearest" not in notes:
        return None
    if any(item["rule_id"] == "POL-EXC" for item in violations):
        return None
    return {
        "rule_id": "POL-EXC",
        "message": "Exception-nearest route requires approval before booking.",
        "cap_amount": None,
        "actual_amount": None,
        "currency": None,
    }


def build_scenario_policy_preview(
    *,
    policy_state: dict[str, Any] | None,
    trip_mode: str,
    estimated_total: Any,
    unresolved_tradeoffs: list[dict[str, Any]] | None = None,
    scenario_notes: list[str] | None = None,
) -> dict[str, Any]:
    """Return a serializable, non-authoritative policy preview for one Compare scenario."""
    base = _preview_base()
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
    notes = [str(item) for item in (scenario_notes or []) if isinstance(item, str)]
    violations: list[dict[str, Any]] = []

    budget_rules = constraint_set.get("budget_rules")
    if isinstance(budget_rules, dict):
        currency_hint = (
            str(estimated_total.get("currency") or "USD")
            if isinstance(estimated_total, dict)
            else "USD"
        )
        violations.extend(_budget_violations(budget_rules, money, currency_hint=currency_hint))

    lodging_rules = constraint_set.get("lodging_rules")
    if isinstance(lodging_rules, dict):
        violations.extend(_lodging_violations(lodging_rules, estimated_total))

    violations.extend(_tradeoff_violations(unresolved_tradeoffs))
    note_violation = _exception_note_violation(notes, violations)
    if note_violation is not None:
        violations.append(note_violation)

    if violations and all(item.get("incomplete") for item in violations):
        return {
            **base,
            "status": "preview_incomplete",
            "status_label": "Trip cost unavailable (preview)",
            "compliant": None,
            "snapshot_available": True,
            "violations": violations,
        }

    compliant = len(violations) == 0
    status_label = "In policy (preview)" if compliant else "Policy issues (preview)"
    return {
        **base,
        "status": "compliant" if compliant else "non_compliant",
        "status_label": status_label,
        "compliant": compliant,
        "snapshot_available": True,
        "violations": violations,
    }


def attach_policy_preview_to_row(
    row: dict[str, Any],
    *,
    policy_state: dict[str, Any] | None,
    trip_mode: str,
    estimated_total: Any,
    unresolved_tradeoffs: list[dict[str, Any]] | None,
    scenario_notes: list[str] | None,
) -> None:
    row["policy_preview"] = build_scenario_policy_preview(
        policy_state=policy_state,
        trip_mode=trip_mode,
        estimated_total=estimated_total,
        unresolved_tradeoffs=unresolved_tradeoffs,
        scenario_notes=scenario_notes,
    )
