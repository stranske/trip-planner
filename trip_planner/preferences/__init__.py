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
    "ANCHOR_SIGNAL_GUIDANCE",
    "Anchor",
    "AutonomyFeedback",
    "AutonomyGuardrails",
    "AutonomyPreference",
    "BudgetModel",
    "ContradictionMarker",
    "DateWindow",
    "DimensionResolutionExplanation",
    "DurationBounds",
    "EvidenceSummary",
    "HardConstraints",
    "HybridFactor",
    "HybridFactorExplanation",
    "InteractionActivation",
    "InteractionRule",
    "LeisurePreferenceProfile",
    "MaterialInfluence",
    "OptionEvidence",
    "PlannerBehaviorMetadata",
    "PlanningAutonomyProfile",
    "PreferenceEvidence",
    "ResolutionExplanation",
    "ResolvedLeisureProfile",
    "RevealedPreferenceSignal",
    "RevealedPreferenceUpdate",
    "TensionFlag",
    "TradeoffDimension",
    "TripFrame",
    "adapt_legacy_request",
    "build_revealed_preference_update",
    "load_legacy_request",
    "resolve_leisure_profile",
    "support_for_anchor_group",
    "support_for_dimension",
    "support_for_hybrid_factor",
    "validate_evidence_support",
]
