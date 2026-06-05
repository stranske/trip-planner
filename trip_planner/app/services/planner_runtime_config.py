"""Configuration helpers for the planner conversation runtime."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from trip_planner.app.services.planner_routing import (
    IntentClassifier,
    KeywordIntentClassifier,
    ModelIntentClassifier,
)

PROPRIETARY_DATA_ZONE = "proprietary"
SYNTHETIC_DATA_ZONE = "synthetic"
AUTHORIZED_OPENAI_ENDPOINT_ENV = "TRIP_PLANNER_OPENAI_AUTHORIZED_ENDPOINT"
AUTHORIZED_MARKERS = frozenset({"1", "true", "yes", "authorized"})


@dataclass(frozen=True, slots=True)
class PlannerRuntimeConfig:
    mode: str
    provider: str | None
    model: str | None
    status: str
    title: str
    summary: str
    fallback_reason: str | None = None
    data_zone: str = SYNTHETIC_DATA_ZONE
    llm_status: str = "deterministic"

    @property
    def model_configured(self) -> bool:
        return self.mode == "model"

    def to_payload(self) -> dict[str, str | None]:
        return {
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "title": self.title,
            "summary": self.summary,
            "fallback_reason": self.fallback_reason,
            "data_zone": self.data_zone,
            "llm_status": self.llm_status,
        }


def get_planner_runtime_config() -> PlannerRuntimeConfig:
    return build_planner_runtime_config(os.environ)


def build_intent_classifier(
    runtime_config: PlannerRuntimeConfig,
    *,
    model: object | None = None,
) -> IntentClassifier:
    if runtime_config.model_configured:
        return ModelIntentClassifier(model)
    return KeywordIntentClassifier()


def build_planner_runtime_config(env: Mapping[str, str]) -> PlannerRuntimeConfig:
    provider = (
        (
            env.get("TRIP_PLANNER_PLANNER_PROVIDER")
            or env.get("TRIP_PLANNER_PLANNER_MODEL_PROVIDER")
            or ""
        )
        .strip()
        .lower()
    )
    model = env.get("TRIP_PLANNER_PLANNER_MODEL", "").strip()
    openai_api_key = env.get("OPENAI_API_KEY", "").strip()
    data_zone = (env.get("TRIP_PLANNER_DATA_ZONE") or SYNTHETIC_DATA_ZONE).strip().lower()
    if data_zone not in {PROPRIETARY_DATA_ZONE, SYNTHETIC_DATA_ZONE}:
        data_zone = SYNTHETIC_DATA_ZONE
    authorized_openai_endpoint = _has_explicit_openai_authorization(env)
    fake_enabled = provider == "fake"
    openai_requested = provider == "openai" and bool(model) and bool(openai_api_key)
    openai_blocked_by_zone = (
        data_zone == PROPRIETARY_DATA_ZONE and openai_requested and not authorized_openai_endpoint
    )
    openai_enabled = openai_requested and not openai_blocked_by_zone

    if fake_enabled or openai_enabled:
        provider_label = provider or "configured"
        return PlannerRuntimeConfig(
            mode="model",
            provider=provider_label,
            model=model or "fake-planner-model",
            status="ready",
            title="Model-backed planner",
            summary="Planner turns use a configured LangChain chat model over explicit app tools.",
            data_zone=data_zone,
            llm_status="authorized" if provider == "openai" else "test-model",
        )

    fallback_reason = "planner_model_not_configured"
    if provider and provider not in {"openai", "fake"}:
        fallback_reason = "unsupported_planner_model_provider"
    elif provider == "openai" and not model:
        fallback_reason = "planner_model_name_missing"
    elif provider == "openai" and model and not openai_api_key:
        fallback_reason = "openai_api_key_missing"
    elif openai_blocked_by_zone:
        fallback_reason = "proprietary_zone_llm_blocked"

    return PlannerRuntimeConfig(
        mode="fallback",
        provider=provider or None,
        model=model or None,
        status="fallback",
        title="Deterministic fallback planner",
        summary="No planner model credentials are configured, so turns use the local deterministic fallback.",
        fallback_reason=fallback_reason,
        data_zone=data_zone,
        llm_status="blocked" if openai_blocked_by_zone else "deterministic",
    )


def _has_explicit_openai_authorization(env: Mapping[str, str]) -> bool:
    marker = env.get(AUTHORIZED_OPENAI_ENDPOINT_ENV, "").strip().lower()
    return marker in AUTHORIZED_MARKERS
