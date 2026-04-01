"""Ingestion scaffolding for normalized option pipelines."""

from ._common import IngestionSummary, IngestionWarning
from .lodging_pipeline import LodgingIngestionResult, ingest_lodging_snapshot
from .transport_pipeline import TransportIngestionResult, ingest_transport_snapshot

__all__ = [
    "IngestionSummary",
    "IngestionWarning",
    "LodgingIngestionResult",
    "TransportIngestionResult",
    "ingest_lodging_snapshot",
    "ingest_transport_snapshot",
]
