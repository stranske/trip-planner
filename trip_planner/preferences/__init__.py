"""Leisure preference contracts and narrow legacy compatibility adapters."""

from .evidence import ContradictionMarker, OptionEvidence, PreferenceEvidence
from .evidence_catalog import (
    ANCHOR_SIGNAL_GUIDANCE,
    support_for_anchor_group,
    support_for_dimension,
    support_for_hybrid_factor,
    validate_evidence_support,
)
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
    "ANCHOR_SIGNAL_GUIDANCE",
    "BudgetModel",
    "ContradictionMarker",
    "DateWindow",
    "DurationBounds",
    "EvidenceSummary",
    "HardConstraints",
    "HybridFactor",
    "InteractionRule",
    "LeisurePreferenceProfile",
    "OptionEvidence",
    "PreferenceEvidence",
    "TensionFlag",
    "TradeoffDimension",
    "TripFrame",
    "adapt_legacy_request",
    "load_legacy_request",
    "support_for_anchor_group",
    "support_for_dimension",
    "support_for_hybrid_factor",
    "validate_evidence_support",
]
