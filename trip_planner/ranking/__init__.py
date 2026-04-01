"""Canonical ranking-result contracts shared by later ranking modules."""

from .explanations import (
    EXPLANATION_RECORD_TYPES,
    EXPLANATION_TARGET_KINDS,
    ExplanationRecord,
)
from .leisure import rank_leisure_candidates
from .models import (
    ADJUSTMENT_KINDS,
    RANK_RESULT_KINDS,
    RISK_SEVERITIES,
    SCHEMA_VERSION,
    RankedResult,
    RankedResultSet,
    RiskFlag,
    ScoreAdjustment,
    ScoreBreakdown,
    ScoreConfidenceSummary,
    ScoreContribution,
)

__all__ = [
    "ADJUSTMENT_KINDS",
    "EXPLANATION_RECORD_TYPES",
    "EXPLANATION_TARGET_KINDS",
    "RANK_RESULT_KINDS",
    "RISK_SEVERITIES",
    "SCHEMA_VERSION",
    "ExplanationRecord",
    "rank_leisure_candidates",
    "RankedResult",
    "RankedResultSet",
    "RiskFlag",
    "ScoreAdjustment",
    "ScoreBreakdown",
    "ScoreConfidenceSummary",
    "ScoreContribution",
]
