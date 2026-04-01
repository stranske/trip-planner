"""Canonical source, adapter, and provenance contracts."""

from .adapters import SourceAdapter
from .models import QualityValueFitSummary, SourceRecord, SourceTrustSignals
from .provenance import ProvenanceReference
from .snapshots import AdapterIssue, NormalizationHandoff, RawSnapshot, RawSourceRecord, SourceQuery

__all__ = [
    "AdapterIssue",
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
