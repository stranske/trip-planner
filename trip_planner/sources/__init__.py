"""Canonical source, adapter, and provenance contracts."""

from .adapters import SourceAdapter
from .dedup import DeduplicationDecision
from .models import QualityValueFitSummary, SourceRecord, SourceTrustSignals
from .provenance import ProvenanceReference
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
    "SourceRecord",
    "SourceQuery",
    "SourceTrustSignals",
]
