"""Leisure preference contracts and narrow legacy compatibility adapters."""

from .legacy_request_adapter import adapt_legacy_request, load_legacy_request
from .models import (
    Anchor,
    BudgetModel,
    DateWindow,
    DurationBounds,
    EvidenceSummary,
    HardConstraints,
    HybridFactor,
    InteractionRule,
    LeisurePreferenceProfile,
    TensionFlag,
    TradeoffDimension,
    TripFrame,
)

__all__ = [
    "Anchor",
    "BudgetModel",
    "DateWindow",
    "DurationBounds",
    "EvidenceSummary",
    "HardConstraints",
    "HybridFactor",
    "InteractionRule",
    "LeisurePreferenceProfile",
    "TensionFlag",
    "TradeoffDimension",
    "TripFrame",
    "adapt_legacy_request",
    "load_legacy_request",
]
