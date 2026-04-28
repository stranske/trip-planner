from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.persistence.models.budget import (
    PersistedActualSpendEvent,
    PersistedBudgetPlan,
    PersistedBudgetPlanVersion,
)
from trip_planner.persistence.models.session import PersistedPlanningSessionState
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.state import (
    ACTUAL_SPEND_SOURCE_KINDS,
    ActualSpendEvent,
    BUDGET_CATEGORY_KEYS,
    BUSINESS_ONLY_BUDGET_CATEGORIES,
    BudgetCategoryAllocation,
    BudgetPlan,
    BudgetScenario,
)


class WorkspaceBudgetNotFoundError(ValueError):
    """Raised when a workspace budget or trip does not exist for the user."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _state_fixture_dir(kind: str) -> Path:
    return _repo_root() / "tests" / "fixtures" / "state" / kind


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _to_currency_amount(value: float | Decimal) -> float:
    return round(float(value), 2)


def _to_decimal_amount(value: float) -> Decimal:
    return Decimal(f"{value:.2f}")


def _next_session_timestamp(current_value: str | None) -> str:
    now = datetime.now(UTC)
    if current_value:
        current_dt = datetime.fromisoformat(current_value.replace("Z", "+00:00"))
        if now <= current_dt:
            now = current_dt + timedelta(microseconds=1)
    return _isoformat(now)


def _owner_profile_id(record: PersistedTrip) -> str:
    if record.mode == "business" and record.business_profile_id:
        return record.business_profile_id
    if record.leisure_profile_id:
        return record.leisure_profile_id
    return f"profile:{record.trip_id}:{record.mode}"


def _ensure_session_record(
    db_session: Session,
    *,
    record: PersistedTrip,
    timestamp: str,
) -> PersistedPlanningSessionState:
    session_record = db_session.get(PersistedPlanningSessionState, f"session:{record.trip_id}")
    if session_record is not None:
        return session_record

    session_record = PersistedPlanningSessionState(
        session_state_id=f"session:{record.trip_id}",
        trip_id=record.trip_id,
        user_id=record.user_id,
        owner_profile_id=_owner_profile_id(record),
        mode=record.mode,
        started_at=_isoformat(record.created_at),
        last_updated_at=timestamp,
        interaction_state={},
        recent_option_presentations=[],
        pending_decisions=[],
        status="active",
        current_checkpoint_id=None,
        current_saved_scenario_id=None,
        active_budget_plan_id=record.budget_state_id,
        activity_log_id=f"activity-log:{record.trip_id}",
        schema_version="0.1.0",
        tags=[],
        notes=["Workspace budget state initialized before planner session activity."],
    )
    db_session.add(session_record)
    db_session.flush()
    return session_record


def _suggested_categories(mode: str) -> list[str]:
    business_only = set(BUSINESS_ONLY_BUDGET_CATEGORIES)
    return [
        category
        for category in BUDGET_CATEGORY_KEYS
        if mode == "business" or category not in business_only
    ]


def _serialize_budget_plan(record: PersistedBudgetPlan) -> dict[str, Any]:
    return BudgetPlan.from_dict(
        {
            "budget_plan_id": record.budget_plan_id,
            "trip_id": record.trip_id,
            "owner_profile_id": record.owner_profile_id,
            "title": record.title,
            "mode": record.mode,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "scenario_budgets": list(record.scenario_budgets),
            "current_scenario_budget_id": record.current_scenario_budget_id,
            "currency": record.currency,
            "schema_version": record.schema_version,
            "tags": list(record.tags),
            "notes": list(record.notes),
        }
    ).to_dict()


def _serialize_spend_event(record: PersistedActualSpendEvent) -> dict[str, Any]:
    return ActualSpendEvent.from_dict(
        {
            "spend_event_id": record.spend_event_id,
            "trip_id": record.trip_id,
            "budget_plan_id": record.budget_plan_id,
            "category_key": record.category_key,
            "amount": _to_currency_amount(record.amount),
            "currency": record.currency,
            "occurred_at": record.occurred_at,
            "source_kind": record.source_kind,
            "source_context": record.source_context,
            "scenario_budget_id": record.scenario_budget_id,
            "saved_scenario_id": record.saved_scenario_id,
            "merchant_name": record.merchant_name,
            "source_ref": record.source_ref,
            "notes": list(record.notes),
        }
    ).to_dict()


def _serialize_version(record: PersistedBudgetPlanVersion) -> dict[str, Any]:
    return {
        "version_id": record.version_id,
        "budget_plan_id": record.budget_plan_id,
        "recorded_at": record.recorded_at,
        "summary": record.summary,
    }


def _build_budget_summary(
    *,
    trip_mode: str,
    budget_plan: dict[str, Any] | None,
    spend_events: list[dict[str, Any]],
    versions: list[dict[str, Any]],
) -> dict[str, Any]:
    current_scenario: dict[str, Any] | None = None
    allocations: list[dict[str, Any]] = []
    currency = "USD"

    if budget_plan is not None:
        currency = budget_plan["currency"]
        current_scenario = next(
            (
                scenario
                for scenario in budget_plan["scenario_budgets"]
                if scenario["scenario_budget_id"] == budget_plan["current_scenario_budget_id"]
            ),
            budget_plan["scenario_budgets"][0] if budget_plan["scenario_budgets"] else None,
        )
        allocations = list(current_scenario["allocations"]) if current_scenario is not None else []

    spend_totals_by_category: dict[str, float] = {}
    for event in spend_events:
        spend_totals_by_category[event["category_key"]] = round(
            spend_totals_by_category.get(event["category_key"], 0.0) + event["amount"],
            2,
        )

    category_summaries: list[dict[str, Any]] = []
    if allocations:
        for allocation in allocations:
            actual_amount = round(spend_totals_by_category.get(allocation["category_key"], 0.0), 2)
            planned_amount = round(allocation["planned_amount"], 2)
            category_summaries.append(
                {
                    "category_key": allocation["category_key"],
                    "label": allocation["label"],
                    "currency": allocation["currency"],
                    "planned_amount": planned_amount,
                    "actual_amount": actual_amount,
                    "remaining_amount": round(planned_amount - actual_amount, 2),
                    "flexibility": allocation["flexibility"],
                }
            )
    else:
        for category in _suggested_categories(trip_mode):
            category_summaries.append(
                {
                    "category_key": category,
                    "label": category.replace("_", " ").title(),
                    "currency": currency,
                    "planned_amount": 0.0,
                    "actual_amount": round(spend_totals_by_category.get(category, 0.0), 2),
                    "remaining_amount": round(-spend_totals_by_category.get(category, 0.0), 2),
                    "flexibility": "flexible",
                }
            )

    planned_total = round(sum(item["planned_amount"] for item in category_summaries), 2)
    actual_total = round(sum(item["actual_amount"] for item in category_summaries), 2)
    return {
        "currency": currency,
        "has_budget_plan": budget_plan is not None,
        "current_scenario_budget_id": (
            budget_plan["current_scenario_budget_id"] if budget_plan else None
        ),
        "current_scenario_title": current_scenario["title"] if current_scenario else None,
        "planned_total": planned_total,
        "actual_total": actual_total,
        "remaining_total": round(planned_total - actual_total, 2),
        "spend_event_count": len(spend_events),
        "version_count": len(versions),
        "suggested_categories": _suggested_categories(trip_mode),
        "category_summaries": category_summaries,
    }


def _budget_fixture_payload(trip_id: str, trip_mode: str) -> dict[str, Any]:
    plan_name = (
        "business_budget_plan.json" if trip_mode == "business" else "leisure_budget_plan.json"
    )
    budget_plan = BudgetPlan.from_dict(
        _load_json(_state_fixture_dir("budget") / plan_name)
    ).to_dict()
    event_payload = _load_json(_state_fixture_dir("budget") / "actual_spend_events.json")
    spend_events = [
        ActualSpendEvent.from_dict(item).to_dict()
        for item in event_payload["events"]
        if item["trip_id"] == trip_id
    ]
    versions = [
        {
            "version_id": f"{budget_plan['budget_plan_id']}-fixture-v1",
            "budget_plan_id": budget_plan["budget_plan_id"],
            "recorded_at": budget_plan["updated_at"],
            "summary": "Fixture budget baseline",
        }
    ]
    return {
        "budget_plan": budget_plan,
        "versions": versions,
        "spend_events": spend_events,
        "summary": _build_budget_summary(
            trip_mode=trip_mode,
            budget_plan=budget_plan,
            spend_events=spend_events,
            versions=versions,
        ),
    }


def _get_owned_trip_record(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> PersistedTrip:
    record = db_session.scalar(
        select(PersistedTrip)
        .where(PersistedTrip.trip_id == trip_id)
        .where(PersistedTrip.user_id == user.user_id)
    )
    if record is None:
        raise WorkspaceBudgetNotFoundError(f"Trip '{trip_id}' was not found.")
    return record


def _load_budget_payload_for_record(
    db_session: Session,
    *,
    record: PersistedTrip,
) -> dict[str, Any]:
    plan_record = db_session.scalar(
        select(PersistedBudgetPlan)
        .where(PersistedBudgetPlan.trip_id == record.trip_id)
        .where(PersistedBudgetPlan.user_id == record.user_id)
        .order_by(PersistedBudgetPlan.updated_at.desc())
    )
    budget_plan = _serialize_budget_plan(plan_record) if plan_record is not None else None
    versions = [
        _serialize_version(item)
        for item in db_session.scalars(
            select(PersistedBudgetPlanVersion)
            .where(PersistedBudgetPlanVersion.trip_id == record.trip_id)
            .order_by(PersistedBudgetPlanVersion.recorded_at.desc())
        ).all()
    ]
    spend_events = [
        _serialize_spend_event(item)
        for item in db_session.scalars(
            select(PersistedActualSpendEvent)
            .where(PersistedActualSpendEvent.trip_id == record.trip_id)
            .order_by(PersistedActualSpendEvent.occurred_at.desc())
        ).all()
    ]
    return {
        "budget_plan": budget_plan,
        "versions": versions,
        "spend_events": spend_events,
        "summary": _build_budget_summary(
            trip_mode=record.mode,
            budget_plan=budget_plan,
            spend_events=spend_events,
            versions=versions,
        ),
    }


def get_workspace_budget_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    return _load_budget_payload_for_record(db_session, record=record)


def build_fixture_budget_payload(*, trip_id: str, trip_mode: str) -> dict[str, Any]:
    return _budget_fixture_payload(trip_id, trip_mode)


def load_budget_payload_for_workspace(
    db_session: Session,
    *,
    record: PersistedTrip,
) -> dict[str, Any]:
    return _load_budget_payload_for_record(db_session, record=record)


def upsert_workspace_budget_plan(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    title: str,
    currency: str,
    current_scenario_budget_id: str | None,
    tags: list[str],
    notes: list[str],
    scenario_budgets: list[dict[str, Any]],
    summary: str = "",
) -> dict[str, Any]:
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    existing = db_session.scalar(
        select(PersistedBudgetPlan)
        .where(PersistedBudgetPlan.trip_id == record.trip_id)
        .where(PersistedBudgetPlan.user_id == record.user_id)
    )
    now = _next_session_timestamp(None)
    plan_id = existing.budget_plan_id if existing is not None else f"budget-plan:{record.trip_id}"
    normalized_scenarios: list[dict[str, Any]] = []
    for index, scenario_payload in enumerate(scenario_budgets):
        scenario_id = (
            scenario_payload.get("scenario_budget_id") or f"{plan_id}:scenario-{index + 1}"
        )
        allocations = [
            BudgetCategoryAllocation(
                category_key=item["category_key"],
                label=item["label"],
                planned_amount=item["planned_amount"],
                currency=item.get("currency", currency),
                flexibility=item.get("flexibility", "flexible"),
                notes=list(item.get("notes", [])),
            ).to_dict()
            for item in scenario_payload["allocations"]
        ]
        normalized_scenarios.append(
            BudgetScenario(
                scenario_budget_id=scenario_id,
                trip_id=record.trip_id,
                title=scenario_payload["title"],
                created_at=existing.created_at if existing is not None else now,
                allocations=[BudgetCategoryAllocation.from_dict(item) for item in allocations],
                currency=currency,
                saved_scenario_id=scenario_payload.get("saved_scenario_id"),
                summary=scenario_payload.get("summary", ""),
                tags=list(scenario_payload.get("tags", [])),
                notes=list(scenario_payload.get("notes", [])),
            ).to_dict()
        )
    current_id = current_scenario_budget_id or normalized_scenarios[0]["scenario_budget_id"]
    budget_plan = BudgetPlan.from_dict(
        {
            "budget_plan_id": plan_id,
            "trip_id": record.trip_id,
            "owner_profile_id": _owner_profile_id(record),
            "title": title,
            "mode": record.mode,
            "created_at": existing.created_at if existing is not None else now,
            "updated_at": now,
            "scenario_budgets": normalized_scenarios,
            "current_scenario_budget_id": current_id,
            "currency": currency,
            "tags": tags,
            "notes": notes,
        }
    )

    if existing is None:
        existing = PersistedBudgetPlan(
            budget_plan_id=budget_plan.budget_plan_id,
            trip_id=record.trip_id,
            user_id=record.user_id,
            owner_profile_id=budget_plan.owner_profile_id,
            title=budget_plan.title,
            mode=budget_plan.mode,
            current_scenario_budget_id=budget_plan.current_scenario_budget_id,
            currency=budget_plan.currency,
            schema_version=budget_plan.schema_version,
            scenario_budgets=budget_plan.to_dict()["scenario_budgets"],
            tags=list(budget_plan.tags),
            notes=list(budget_plan.notes),
            created_at=budget_plan.created_at,
            updated_at=budget_plan.updated_at,
        )
        db_session.add(existing)
    else:
        existing.owner_profile_id = budget_plan.owner_profile_id
        existing.title = budget_plan.title
        existing.mode = budget_plan.mode
        existing.current_scenario_budget_id = budget_plan.current_scenario_budget_id
        existing.currency = budget_plan.currency
        existing.schema_version = budget_plan.schema_version
        existing.scenario_budgets = budget_plan.to_dict()["scenario_budgets"]
        existing.tags = list(budget_plan.tags)
        existing.notes = list(budget_plan.notes)
        existing.updated_at = budget_plan.updated_at

    record.budget_state_id = budget_plan.budget_plan_id
    session_record = _ensure_session_record(db_session, record=record, timestamp=now)
    session_record.active_budget_plan_id = budget_plan.budget_plan_id
    session_record.last_updated_at = now
    record.updated_at = datetime.now(UTC)

    db_session.add(
        PersistedBudgetPlanVersion(
            version_id=f"{budget_plan.budget_plan_id}-v{secrets.token_hex(4)}",
            budget_plan_id=budget_plan.budget_plan_id,
            trip_id=record.trip_id,
            recorded_at=budget_plan.updated_at,
            summary=summary or "Budget plan updated",
            snapshot=budget_plan.to_dict(),
        )
    )
    db_session.commit()
    return _load_budget_payload_for_record(db_session, record=record)


def record_workspace_spend_event(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    category_key: str,
    amount: float,
    currency: str | None,
    occurred_at: str | None,
    source_kind: str,
    source_context: str,
    scenario_budget_id: str | None,
    saved_scenario_id: str | None,
    merchant_name: str,
    source_ref: str | None,
    notes: list[str],
) -> dict[str, Any]:
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    plan_record = db_session.scalar(
        select(PersistedBudgetPlan)
        .where(PersistedBudgetPlan.trip_id == record.trip_id)
        .where(PersistedBudgetPlan.user_id == record.user_id)
    )
    if plan_record is None:
        raise WorkspaceBudgetNotFoundError(
            f"Trip '{trip_id}' does not have a persisted budget plan yet."
        )
    event_currency = plan_record.currency
    if currency is not None:
        normalized_currency = currency.strip().upper()
        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            raise ValueError("currency must be a 3-letter ISO currency code")
        if normalized_currency != plan_record.currency:
            raise ValueError("currency must match the persisted budget plan currency")
        event_currency = normalized_currency
    now = _isoformat(datetime.now(UTC))
    event = ActualSpendEvent(
        spend_event_id=f"spend:{record.trip_id}:{secrets.token_hex(4)}",
        trip_id=record.trip_id,
        budget_plan_id=plan_record.budget_plan_id,
        category_key=category_key,
        amount=amount,
        currency=event_currency,
        occurred_at=occurred_at or now,
        source_kind=source_kind,
        source_context=source_context,
        scenario_budget_id=scenario_budget_id,
        saved_scenario_id=saved_scenario_id,
        merchant_name=merchant_name,
        source_ref=source_ref,
        notes=notes,
    )
    db_session.add(
        PersistedActualSpendEvent(
            spend_event_id=event.spend_event_id,
            trip_id=event.trip_id,
            budget_plan_id=event.budget_plan_id,
            category_key=event.category_key,
            amount=_to_decimal_amount(event.amount),
            currency=event.currency,
            occurred_at=event.occurred_at,
            source_kind=event.source_kind,
            source_context=event.source_context,
            scenario_budget_id=event.scenario_budget_id,
            saved_scenario_id=event.saved_scenario_id,
            merchant_name=event.merchant_name,
            source_ref=event.source_ref,
            notes=list(event.notes),
        )
    )
    session_record = _ensure_session_record(db_session, record=record, timestamp=now)
    session_record.active_budget_plan_id = plan_record.budget_plan_id
    session_record.last_updated_at = _next_session_timestamp(session_record.last_updated_at)
    record.updated_at = datetime.now(UTC)
    db_session.commit()
    return _load_budget_payload_for_record(db_session, record=record)


def update_workspace_spend_event(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    spend_event_id: str,
    category_key: str,
    amount: float,
    currency: str | None,
    occurred_at: str | None,
    source_kind: str,
    source_context: str,
    scenario_budget_id: str | None,
    saved_scenario_id: str | None,
    merchant_name: str,
    source_ref: str | None,
    notes: list[str],
) -> dict[str, Any]:
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    event_record = db_session.get(PersistedActualSpendEvent, spend_event_id)
    if event_record is None or event_record.trip_id != record.trip_id:
        raise WorkspaceBudgetNotFoundError(
            f"Spend event '{spend_event_id}' was not found for trip '{trip_id}'."
        )
    if source_kind not in ACTUAL_SPEND_SOURCE_KINDS:
        raise ValueError(f"source_kind must be one of {ACTUAL_SPEND_SOURCE_KINDS}")
    if category_key not in BUDGET_CATEGORY_KEYS:
        raise ValueError(f"category_key must be one of {BUDGET_CATEGORY_KEYS}")
    updated_currency = event_record.currency
    if currency is not None:
        normalized_currency = currency.strip().upper()
        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            raise ValueError("currency must be a 3-letter ISO currency code")
        if normalized_currency != event_record.currency:
            raise ValueError("currency cannot be changed for an existing spend event")
        updated_currency = normalized_currency
    now = _next_session_timestamp(None)
    event_record.category_key = category_key
    event_record.amount = _to_decimal_amount(amount)
    event_record.currency = updated_currency
    event_record.occurred_at = occurred_at or event_record.occurred_at
    event_record.source_kind = source_kind
    event_record.source_context = source_context
    event_record.scenario_budget_id = scenario_budget_id
    event_record.saved_scenario_id = saved_scenario_id
    event_record.merchant_name = merchant_name
    event_record.source_ref = source_ref
    event_record.notes = list(notes)
    session_record = _ensure_session_record(db_session, record=record, timestamp=now)
    session_record.active_budget_plan_id = event_record.budget_plan_id
    session_record.last_updated_at = _next_session_timestamp(session_record.last_updated_at)
    record.updated_at = datetime.now(UTC)
    db_session.commit()
    return _load_budget_payload_for_record(db_session, record=record)
