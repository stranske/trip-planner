"""Canonical source, adapter, and provenance contracts."""

from .adapters import SourceAdapter
from .dedup import DeduplicationDecision
from .models import QualityValueFitSummary, SourceRecord, SourceTrustSignals
from .provenance import ProvenanceReference
from .quality import (
    CONFIDENCE_LABELS,
    SourceConfidenceSummary,
    SourceQualityScore,
    SourceQualityScorer,
    summarize_sources,
)
from .resolution import (
    AttributeConflict,
    EntityResolution,
    MatchCandidate,
    MergedEntityProvenance,
)
from .snapshots import (
    AdapterIssue,
    NormalizationHandoff,
    RawSnapshot,
    RawSourceRecord,
    SourceQuery,
)

__all__ = [
    "CONFIDENCE_LABELS",
    "AdapterIssue",
    "AttributeConflict",
    "DeduplicationDecision",
    "EntityResolution",
    "MatchCandidate",
    "MergedEntityProvenance",
    "NormalizationHandoff",
    "ProvenanceReference",
    "QualityValueFitSummary",
    "RawSnapshot",
    "RawSourceRecord",
    "SourceAdapter",
    "SourceConfidenceSummary",
    "SourceQualityScore",
    "SourceQualityScorer",
    "SourceQuery",
    "SourceRecord",
    "SourceTrustSignals",
    "summarize_sources",
]
