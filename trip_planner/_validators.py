"""Shared validation helpers for lightweight planning contracts."""

from __future__ import annotations

from typing import Any


def require_non_empty(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} is required")


def require_optional_non_empty(value: str | None, field_name: str) -> None:
    if value is not None and not value:
        raise ValueError(f"{field_name} must be non-empty when provided")


def require_probability(value: float, field_name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


def require_non_negative(value: float | int, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def require_strings(values: list[str], field_name: str) -> None:
    if any(not isinstance(item, str) or not item for item in values):
        raise ValueError(f"{field_name} must contain only non-empty strings")


def require_float_mapping(mapping: dict[str, float], field_name: str) -> None:
    if any(not isinstance(key, str) or not key for key in mapping):
        raise ValueError(f"{field_name} must use non-empty string keys")
    for key, value in mapping.items():
        require_probability(value, f"{field_name}[{key}]")


def require_string_mapping(mapping: dict[str, Any], field_name: str) -> None:
    if any(not isinstance(key, str) or not key for key in mapping):
        raise ValueError(f"{field_name} must use non-empty string keys")
