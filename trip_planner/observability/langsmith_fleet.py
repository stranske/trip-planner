"""Build dashboard-safe LangSmith fleet records for planner turns.

The shared schema is owned by `stranske/Workflows#2150`; this module emits the
trip-planner-specific `langsmith-fleet/v1` records for trip-scoped planner
conversation runs. Records deliberately avoid raw traveler messages, prompt
text, and itinerary payloads. They keep only stable IDs, counts, statuses, and
bounded domain metadata useful for fleet dashboards.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Final, Literal

SCHEMA_VERSION: Final = "langsmith-fleet/v1"
REPO: Final = "stranske/trip-planner"
SURFACE: Final = "planner-conversation"
GITHUB_ISSUE: Final = "stranske/trip-planner#1208"
ARTIFACT_NAME: Final = "langsmith-fleet.ndjson"
DEFAULT_PROJECT: Final = "trip-planner"
ENV_LANGSMITH_KEY: Final = "LANGSMITH_API_KEY"
ENV_LANGCHAIN_PROJECT: Final = "LANGCHAIN_PROJECT"
ENV_LANGSMITH_PROJECT: Final = "LANGSMITH_PROJECT"
ENV_LANGCHAIN_TRACING_V2: Final = "LANGCHAIN_TRACING_V2"
ENV_LANGCHAIN_API_KEY: Final = "LANGCHAIN_API_KEY"
ENV_FLEET_PATH: Final = "TRIP_PLANNER_LANGSMITH_FLEET_PATH"
_KNOWN_CONTEXT_SECTIONS: Final = {
    "trip",
    "planner_panel_state",
    "autonomy_preferences",
    "budget_state",
    "policy_state",
    "proposal_state",
    "runtime_scenario_comparison",
    "planning_ledger",
    "recent_activity",
}

Status = Literal["success", "error", "fallback", "no_secret"]


@dataclass(frozen=True, slots=True)
class PlannerFleetContext:
    """Shared trace context for one planner conversation turn."""

    run_id: str
    session_id: str
    trip_id: str
    planning_mode: str | None = None
    provider: str | None = None
    model: str | None = None
    trace_id: str | None = None
    trace_url: str | None = None
    recorded_at: str | None = None
    github_pr: str | None = None


def ensure_langsmith_project_defaults() -> bool:
    """Apply trip-planner LangSmith defaults when a key is present."""

    api_key = os.environ.get(ENV_LANGSMITH_KEY, "").strip()
    if not api_key:
        return False
    os.environ.setdefault(ENV_LANGCHAIN_TRACING_V2, "true")
    os.environ.setdefault(ENV_LANGCHAIN_PROJECT, DEFAULT_PROJECT)
    os.environ.setdefault(ENV_LANGSMITH_PROJECT, DEFAULT_PROJECT)
    os.environ.setdefault(ENV_LANGCHAIN_API_KEY, api_key)
    return True


def build_langsmith_run_config(
    *,
    context: PlannerFleetContext,
    metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return LangChain config metadata when LangSmith is enabled."""

    if not ensure_langsmith_project_defaults():
        return None
    return {
        "run_name": "trip-planner.planner-conversation",
        "tags": [
            "repo:trip-planner",
            "surface:planner-conversation",
            f"planning_mode:{context.planning_mode or 'unknown'}",
        ],
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "repo": REPO,
            "surface": SURFACE,
            "github_issue": GITHUB_ISSUE,
            "run_id": context.run_id,
            "session_id": context.session_id,
            "trip_id_hash": _hash_identifier(context.trip_id),
            "planning_mode": context.planning_mode,
            "provider": context.provider,
            "model": context.model,
            "task_class": metadata.get("task_class"),
            "plan_maturity": metadata.get("plan_maturity"),
        },
    }


def build_planner_fleet_records(
    *,
    context: PlannerFleetContext,
    runtime_mode: str,
    turn_metadata: Mapping[str, Any],
    tool_calls: Iterable[Mapping[str, Any]],
    context_readiness: Mapping[str, Any],
    artifact_ref: str | None = None,
) -> list[dict[str, Any]]:
    """Return one Workflows-compatible fleet record for a planner run."""

    tracing_enabled = ensure_langsmith_project_defaults()
    calls = [dict(item) for item in tool_calls]
    failed_calls = [item for item in calls if str(item.get("status") or "") == "error"]
    fallback_reason = turn_metadata.get("fallback_reason")
    if failed_calls:
        status: Status = "error"
    elif not os.environ.get(ENV_LANGSMITH_KEY, "").strip():
        status = "no_secret"
    elif runtime_mode == "fallback" or fallback_reason:
        status = "fallback"
    elif tracing_enabled:
        status = "success"
    else:
        status = "no_secret"

    domain = {
        "session_id_hash": _hash_identifier(context.session_id),
        "trip_id_hash": _hash_identifier(context.trip_id),
        "planning_mode": context.planning_mode or "unknown",
        "planner_action": turn_metadata.get("task_class") or "unknown",
        "itinerary_phase": turn_metadata.get("plan_maturity") or "unknown",
        "provider_state": turn_metadata.get("provider_state") or runtime_mode,
        "fallback_state": fallback_reason or "none",
        "error_state": "tool_error" if failed_calls else "none",
        "tool_call_count": len(calls),
        "failed_tool_call_count": len(failed_calls),
        "mutating_tool_call_count": sum(1 for item in calls if bool(item.get("mutates_state"))),
        "inventory_usage": _tool_state(calls, {"refresh_inventory"}),
        "budget_constraint_status": _tool_state(calls, {"read_budget_state", "update_budget_plan"}),
        "itinerary_coherence_status": _tool_state(
            calls,
            {"refresh_scenarios", "refresh_route_comparison", "read_route_geometry"},
        ),
        "persisted_workspace_result": "available",
        "context_readiness_status": context_readiness.get("status") or "unknown",
        "missing_context_sections": _safe_context_sections(
            context_readiness.get("missing_sections") or []
        ),
    }
    return [
        _record(
            context=context,
            status=status,
            recorded_at=context.recorded_at or _utc_timestamp(),
            domain=domain,
            error_code=_first_error_category(failed_calls),
            artifact_ref=artifact_ref,
        )
    ]


def default_fleet_artifact_path() -> Path:
    """Return the default NDJSON path used by the planner surface."""

    override = os.environ.get(ENV_FLEET_PATH, "").strip()
    if override:
        return Path(override).expanduser()
    root = _project_root(Path(__file__).resolve())
    return root / "artifacts" / "langsmith" / ARTIFACT_NAME


def write_fleet_records(path: Path, records: Iterable[Mapping[str, Any]]) -> Path:
    """Write fleet records as deterministic NDJSON and return the path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(dict(record), sort_keys=True, separators=(",", ":")) for record in records]
    payload = "\n".join(lines)
    if lines:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")
    return path


def append_fleet_records(
    path: Path,
    records: Iterable[Mapping[str, Any]],
    *,
    retention_limit: int = 2_000,
) -> Path:
    """Append fleet records as NDJSON with bounded local retention."""

    if retention_limit < 1:
        raise ValueError("retention_limit must be >= 1")
    materialized = [dict(record) for record in records]
    if not materialized:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl_module: ModuleType | None = None
        with suppress(ImportError):
            import fcntl as fcntl_module
        if fcntl_module is not None:
            with suppress(OSError):
                fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_EX)
        for record in materialized:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        handle.seek(0)
        lines = handle.read().splitlines()
        if len(lines) > retention_limit:
            trimmed = lines[-retention_limit:]
            temp_path = path.with_suffix(path.suffix + ".tmp")
            temp_path.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
            temp_path.replace(path)
        if fcntl_module is not None:
            with suppress(Exception):
                fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_UN)
    return path


def _record(
    *,
    context: PlannerFleetContext,
    status: Status,
    recorded_at: str,
    domain: Mapping[str, Any],
    error_code: str | None,
    artifact_ref: str | None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "repo": REPO,
        "surface": SURFACE,
        "operation": "planner-turn",
        "run_id": context.run_id,
        "status": status,
        "github_issue": GITHUB_ISSUE,
        "recorded_at": recorded_at,
        "domain": dict(domain),
    }
    if context.github_pr:
        record["github_pr"] = context.github_pr
    if context.provider:
        record["provider"] = context.provider
    if context.model:
        record["model"] = context.model
    if context.trace_id:
        record["trace_id"] = context.trace_id
    if context.trace_url:
        record["trace_url"] = context.trace_url
    if artifact_ref:
        record["artifact_ref"] = artifact_ref
    if error_code:
        record["error_category"] = error_code
    return record


def _tool_state(calls: list[dict[str, Any]], names: set[str]) -> str:
    matched = [item for item in calls if str(item.get("tool_name") or "") in names]
    if not matched:
        return "not_requested"
    if any(str(item.get("status") or "") == "error" for item in matched):
        return "error"
    if any(str(item.get("status") or "") in {"completed", "partial"} for item in matched):
        return "used"
    return "unavailable"


def _safe_context_sections(sections: Iterable[Any]) -> list[str]:
    safe_sections: list[str] = []
    for section in sections:
        name = str(section).strip()
        if not name:
            continue
        safe_sections.append(name if name in _KNOWN_CONTEXT_SECTIONS else "other")
    return [item for item in dict.fromkeys(safe_sections)]


def _first_error_category(failed_calls: list[dict[str, Any]]) -> str | None:
    if not failed_calls:
        return None
    return str(failed_calls[0].get("tool_name") or "planner_tool_error")


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate
    return Path.cwd()


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
