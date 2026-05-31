"""Leisure preference contracts and narrow legacy compatibility adapters."""

from .autonomy import (
    AutonomyFeedback,
    AutonomyGuardrails,
    AutonomyPreference,
    PlannerBehaviorMetadata,
    PlanningAutonomyProfile,
)
from .evidence import ContradictionMarker, OptionEvidence, PreferenceEvidence
from .evidence_catalog import (
    ANCHOR_SIGNAL_GUIDANCE,
    support_for_anchor_group,
    support_for_dimension,
    support_for_hybrid_factor,
    validate_evidence_support,
)
from .explanations import (
    DimensionResolutionExplanation,
    HybridFactorExplanation,
    InteractionActivation,
    MaterialInfluence,
    ResolutionExplanation,
    ResolvedLeisureProfile,
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
from .resolution import resolve_leisure_profile
from .revealed_preference import (
    RevealedPreferenceSignal,
    RevealedPreferenceUpdate,
    build_revealed_preference_update,
)

__all__ = [
    "Anchor",
    "ANCHOR_SIGNAL_GUIDANCE",
    "AutonomyFeedback",
    "AutonomyGuardrails",
    "AutonomyPreference",
    "BudgetModel",
    "build_revealed_preference_update",
    "ContradictionMarker",
    "DateWindow",
    "DurationBounds",
    "DimensionResolutionExplanation",
    "EvidenceSummary",
    "HardConstraints",
    "HybridFactor",
    "HybridFactorExplanation",
    "InteractionRule",
    "InteractionActivation",
    "MaterialInfluence",
    "LeisurePreferenceProfile",
    "OptionEvidence",
    "PlannerBehaviorMetadata",
    "PlanningAutonomyProfile",
    "PreferenceEvidence",
    "RevealedPreferenceSignal",
    "RevealedPreferenceUpdate",
    "ResolutionExplanation",
    "ResolvedLeisureProfile",
    "TensionFlag",
    "TradeoffDimension",
    "TripFrame",
    "adapt_legacy_request",
    "load_legacy_request",
    "resolve_leisure_profile",
    "support_for_anchor_group",
    "support_for_dimension",
    "support_for_hybrid_factor",
    "validate_evidence_support",
]
