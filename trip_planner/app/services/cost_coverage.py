"""Evidence-aware business-trip cost coverage and assisted research."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.planner_runtime_config import get_planner_runtime_config
from trip_planner.app.services.workspace import WorkspaceTripNotFoundError, _get_owned_trip_record
from trip_planner.persistence.models.account import UserAccount

_DEFAULT_CONTRACT_VERSION = "tpp-intake-requirements/v1"
_COVERAGE_STATUSES = {
    "needs_input",
    "research_ready",
    "researched",
    "estimated",
    "evidenced",
    "complete",
    "not_applicable",
}
_PROFILE_INPUT_KEYS = {
    "traveler_residence_address",
    "official_domicile_address",
}


class CostCoverageUnavailableError(RuntimeError):
    """Raised when organization requirements cannot be loaded safely."""


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_tpp_catalog() -> dict[str, Any]:
    base_url = os.getenv("TPP_BASE_URL", "").strip().rstrip("/")
    token = os.getenv("TPP_ACCESS_TOKEN", "").strip()
    if not base_url or not token:
        raise CostCoverageUnavailableError(
            "TPP intake requirements are unavailable because the planner transport is not configured."
        )
    request = urllib.request.Request(
        f"{base_url}/api/planner/intake-requirements",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CostCoverageUnavailableError(
            "TPP intake requirements could not be loaded."
        ) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("requirements"), list):
        raise CostCoverageUnavailableError("TPP returned a malformed intake requirement catalog.")
    return payload


def _automatic_inputs(record: Any) -> dict[str, str]:
    travel_dates = ""
    if record.start_date and record.end_date:
        travel_dates = f"{record.start_date} to {record.end_date}"
    destination = ", ".join(record.primary_regions or [])
    zip_match = re.search(r"\b\d{5}(?:-\d{4})?\b", destination)
    return {
        "travel_dates": travel_dates,
        "parking_days": str(record.duration_days or ""),
        "trip_duration_days": str(record.duration_days or ""),
        "destination": destination,
        "destination_zip": zip_match.group(0) if zip_match else "",
    }


def _merge_requirement_state(
    requirement: dict[str, Any],
    stored: dict[str, Any],
    automatic_inputs: dict[str, str],
) -> dict[str, Any]:
    inputs = {
        **{key: value for key, value in automatic_inputs.items() if value},
        **{
            str(key): str(value)
            for key, value in dict(stored.get("inputs") or {}).items()
            if str(value).strip()
        },
    }
    required_inputs = [str(item) for item in requirement.get("required_inputs") or []]
    missing_inputs = [item for item in required_inputs if not inputs.get(item, "").strip()]
    collection_mode = str(requirement.get("collection_mode") or "traveler")
    default_status = (
        "needs_input"
        if missing_inputs
        else "research_ready" if collection_mode == "researchable" else "needs_input"
    )
    return {
        **requirement,
        "status": str(stored.get("status") or default_status),
        "inputs": inputs,
        "missing_inputs": missing_inputs,
        "estimate_amount": stored.get("estimate_amount"),
        "currency": str(stored.get("currency") or "USD"),
        "note": str(stored.get("note") or ""),
        "source_url": str(stored.get("source_url") or ""),
        "research": stored.get("research"),
        "selected_option": stored.get("selected_option"),
        "updated_at": stored.get("updated_at"),
    }


def _summary(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    resolved = {"complete", "not_applicable", "evidenced"}
    researchable = [
        item
        for item in requirements
        if item.get("collection_mode") == "researchable" and item.get("status") not in resolved
    ]
    return {
        "requirement_count": len(requirements),
        "resolved_count": sum(item.get("status") in resolved for item in requirements),
        "research_offer_count": len(researchable),
        "ready_for_handoff": all(item.get("status") in resolved for item in requirements),
        "headline": (
            "Cost and evidence coverage is complete."
            if requirements and all(item.get("status") in resolved for item in requirements)
            else "The planner can research missing trip costs and evidence."
        ),
    }


def get_cost_coverage_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any]:
    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except ValueError as error:
        raise WorkspaceTripNotFoundError(str(error)) from error
    try:
        catalog = _load_tpp_catalog()
        source_status = "live_tpp"
    except CostCoverageUnavailableError as error:
        state = dict(record.cost_coverage_state or {})
        cached = state.get("catalog")
        if not isinstance(cached, dict):
            return {
                "trip_id": trip_id,
                "contract_version": _DEFAULT_CONTRACT_VERSION,
                "source_status": "unavailable",
                "summary": {
                    "requirement_count": 0,
                    "resolved_count": 0,
                    "research_offer_count": 0,
                    "ready_for_handoff": False,
                    "headline": str(error),
                },
                "requirements": [],
            }
        catalog = cached
        source_status = "cached_tpp"

    state = dict(record.cost_coverage_state or {})
    account = db_session.get(UserAccount, user.user_id)
    profile_inputs = (
        {
            str(key): str(value)
            for key, value in dict(account.travel_profile_state or {}).items()
            if str(value).strip()
        }
        if account is not None
        else {}
    )
    stored_items = {
        str(item.get("code")): item
        for item in list(state.get("items") or [])
        if isinstance(item, dict) and item.get("code")
    }
    item_inputs = {
        str(key): str(value)
        for item in stored_items.values()
        for key, value in dict(item.get("inputs") or {}).items()
        if str(value).strip()
    }
    shared_inputs = {
        **profile_inputs,
        **item_inputs,
        **{
            str(key): str(value)
            for key, value in dict(state.get("shared_inputs") or {}).items()
            if str(value).strip()
        },
    }
    automatic_inputs = {**_automatic_inputs(record), **shared_inputs}
    requirements = [
        _merge_requirement_state(
            item, stored_items.get(str(item.get("code")), {}), automatic_inputs
        )
        for item in catalog.get("requirements") or []
        if isinstance(item, dict) and item.get("code")
    ]
    record.cost_coverage_state = {
        **state,
        "shared_inputs": shared_inputs,
        "catalog": catalog,
        "contract_version": catalog.get("contract_version", _DEFAULT_CONTRACT_VERSION),
        "items": [
            {key: value for key, value in item.items() if key not in {"missing_inputs"}}
            for item in requirements
        ],
    }
    db_session.commit()
    return {
        "trip_id": trip_id,
        "contract_version": str(catalog.get("contract_version") or _DEFAULT_CONTRACT_VERSION),
        "source_status": source_status,
        "summary": _summary(requirements),
        "requirements": requirements,
    }


def update_cost_coverage_item(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    requirement_code: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    current = get_cost_coverage_payload(db_session, user=user, trip_id=trip_id)
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    requirements = list(current["requirements"])
    target = next(
        (item for item in requirements if item.get("code") == requirement_code),
        None,
    )
    if target is None:
        raise ValueError(f"Unknown cost coverage requirement '{requirement_code}'.")
    status = updates.get("status")
    if status is not None and status not in _COVERAGE_STATUSES:
        raise ValueError(f"Unsupported cost coverage status '{status}'.")
    merged = {
        **target,
        **{key: value for key, value in updates.items() if value is not None},
        "inputs": {**dict(target.get("inputs") or {}), **dict(updates.get("inputs") or {})},
        "updated_at": _iso_now(),
    }
    if merged.get("selected_option") and updates.get("status") is None:
        merged["status"] = "evidenced" if merged.get("source_url") else "estimated"
    requirements = [
        merged if item.get("code") == requirement_code else item for item in requirements
    ]
    state = dict(record.cost_coverage_state or {})
    shared_inputs = {
        **dict(state.get("shared_inputs") or {}),
        **{
            str(key): str(value)
            for key, value in dict(updates.get("inputs") or {}).items()
            if str(value).strip()
        },
    }
    account = db_session.get(UserAccount, user.user_id)
    if account is not None:
        profile_updates = {
            str(key): str(value).strip()
            for key, value in dict(updates.get("inputs") or {}).items()
            if key in _PROFILE_INPUT_KEYS and str(value).strip()
        }
        if profile_updates:
            account.travel_profile_state = {
                **dict(account.travel_profile_state or {}),
                **profile_updates,
            }
    record.cost_coverage_state = {
        **state,
        "shared_inputs": shared_inputs,
        "items": requirements,
    }
    db_session.commit()
    return get_cost_coverage_payload(db_session, user=user, trip_id=trip_id)


def _response_sources(response: Any) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "web_search_call":
            continue
        action = getattr(item, "action", None)
        for source in getattr(action, "sources", []) or []:
            url = str(getattr(source, "url", "") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(
                {
                    "title": str(getattr(source, "title", "") or "Source"),
                    "url": url,
                }
            )
    return sources[:12]


def _parse_research_output(text: str) -> tuple[str, list[dict[str, Any]]]:
    candidate = text.strip()
    candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.I)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return text.strip(), []
    if not isinstance(payload, dict):
        return text.strip(), []
    options = [item for item in payload.get("options") or [] if isinstance(item, dict)][:8]
    return str(payload.get("summary") or "Research completed."), options


def research_cost_coverage_item(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    requirement_code: str,
    inputs: dict[str, str],
) -> dict[str, Any]:
    current = update_cost_coverage_item(
        db_session,
        user=user,
        trip_id=trip_id,
        requirement_code=requirement_code,
        updates={"inputs": inputs},
    )
    requirement = next(
        item for item in current["requirements"] if item.get("code") == requirement_code
    )
    if requirement.get("collection_mode") not in {"researchable", "automatic"}:
        raise ValueError("This requirement needs traveler or organization input.")
    missing = list(requirement.get("missing_inputs") or [])
    if missing:
        return {
            **current,
            "research_notice": {
                "status": "needs_input",
                "missing_inputs": missing,
                "message": "Add the highlighted trip details and the planner can research this.",
            },
        }

    runtime = get_planner_runtime_config()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if runtime.mode != "model" or runtime.provider != "openai" or not api_key:
        raise CostCoverageUnavailableError(
            "Live evidence research requires the authorized OpenAI planner runtime."
        )
    from openai import OpenAI

    trip = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    context = {
        "trip_dates": f"{trip.start_date} to {trip.end_date}",
        "destination": list(trip.primary_regions or []),
        "duration_days": trip.duration_days,
        "inputs": requirement.get("inputs") or {},
    }
    prompt = (
        "You are researching one anticipated business-travel cost. Use current public web "
        "sources, prefer official providers, never book or submit anything, and do not invent "
        "missing rates. Return ONLY valid JSON with keys summary and options. options must be "
        "an array of objects with name, unit_rate (number or null), unit, estimated_total "
        "(number or null), notes, source_url, and a details object for structured facts needed "
        "by the named output fields. For a meal allowance, return one option whose details "
        "include eligible_breakfasts, eligible_lunches, eligible_dinners, meals_provided, and "
        "meal_per_diem_requested. For airport access, include mode, reimbursable_miles, "
        "mileage_cost, rideshare_total, home_to_airport_miles, office_to_airport_miles, and "
        "route_rule; apply the organization's supplied 2026 workbook rate of $0.725 per "
        "reimbursable mile and do not count ordinary home-to-office commuting. For airport "
        "parking, compare airport-operated lots with reputable off-airport shuttle operators; "
        "do not default to either category or to an operator the traveler used previously. "
        "No markdown fences.\n\n"
        f"Requirement: {requirement.get('title')}\n"
        f"Research task: {requirement.get('research_prompt')}\n"
        f"Trip context: {json.dumps(context, default=str)}"
    )
    response = OpenAI(api_key=api_key).responses.create(
        model=runtime.model or "gpt-5.6-sol",
        tools=[{"type": "web_search"}],
        include=["web_search_call.action.sources"],
        input=prompt,
    )
    summary, options = _parse_research_output(response.output_text)
    sources = _response_sources(response)
    research = {
        "status": "completed",
        "summary": summary,
        "options": options,
        "sources": sources,
        "researched_at": _iso_now(),
        "model": runtime.model,
    }
    return update_cost_coverage_item(
        db_session,
        user=user,
        trip_id=trip_id,
        requirement_code=requirement_code,
        updates={"status": "researched", "research": research},
    )
