"""Canonical ranking-result contracts shared by later ranking modules."""

from .business import BusinessRankingEngine
from .explanations import (
    EXPLANATION_RECORD_TYPES,
    EXPLANATION_TARGET_KINDS,
    ExplanationRecord,
    build_source_confidence_explanation,
)
from .leisure import LeisureRankingEngine
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
    "BusinessRankingEngine",
    "RANK_RESULT_KINDS",
    "RISK_SEVERITIES",
    "SCHEMA_VERSION",
    "ExplanationRecord",
    "LeisureRankingEngine",
    "RankedResult",
    "RankedResultSet",
    "RiskFlag",
    "ScoreAdjustment",
    "ScoreBreakdown",
    "ScoreConfidenceSummary",
    "ScoreContribution",
    "build_source_confidence_explanation",
]
