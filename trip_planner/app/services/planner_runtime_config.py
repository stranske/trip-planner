"""Configuration helpers for the planner conversation runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlannerRuntimeConfig:
    mode: str
    provider: str | None
    model: str | None
    status: str
    title: str
    summary: str
    fallback_reason: str | None = None

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
        }


def get_planner_runtime_config() -> PlannerRuntimeConfig:
    provider = (
        os.getenv("TRIP_PLANNER_PLANNER_PROVIDER")
        or os.getenv("TRIP_PLANNER_PLANNER_MODEL_PROVIDER")
        or ""
    ).strip().lower()
    model = os.getenv("TRIP_PLANNER_PLANNER_MODEL", "").strip()
    fake_enabled = provider == "fake"
    openai_enabled = provider == "openai" and bool(model) and bool(os.getenv("OPENAI_API_KEY"))

    if fake_enabled or openai_enabled:
        provider_label = provider or "configured"
        return PlannerRuntimeConfig(
            mode="model",
            provider=provider_label,
            model=model or "fake-planner-model",
            status="ready",
            title="Model-backed planner",
            summary="Planner turns use a configured LangChain chat model over explicit app tools.",
        )

    fallback_reason = "planner_model_not_configured"
    if provider and provider not in {"openai", "fake"}:
        fallback_reason = "unsupported_planner_model_provider"
    elif provider == "openai" and not model:
        fallback_reason = "planner_model_name_missing"
    elif provider == "openai" and model and not os.getenv("OPENAI_API_KEY"):
        fallback_reason = "openai_api_key_missing"

    return PlannerRuntimeConfig(
        mode="fallback",
        provider=provider or None,
        model=model or None,
        status="fallback",
        title="Deterministic fallback planner",
        summary="No planner model credentials are configured, so turns use the local deterministic fallback.",
        fallback_reason=fallback_reason,
    )
