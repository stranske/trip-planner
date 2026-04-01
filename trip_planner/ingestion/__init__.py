"""Ingestion scaffolding for normalized option pipelines."""

from ._common import IngestionSummary, IngestionWarning
from .activity_pipeline import ActivityIngestionResult, ingest_activity_snapshot
from .destination_pipeline import DestinationIngestionResult, ingest_destination_snapshot
from .lodging_pipeline import LodgingIngestionResult, ingest_lodging_snapshot
from .transport_pipeline import TransportIngestionResult, ingest_transport_snapshot

__all__ = [
    "ActivityIngestionResult",
    "DestinationIngestionResult",
    "IngestionSummary",
    "IngestionWarning",
    "LodgingIngestionResult",
    "TransportIngestionResult",
    "ingest_activity_snapshot",
    "ingest_destination_snapshot",
    "ingest_lodging_snapshot",
    "ingest_transport_snapshot",
]
