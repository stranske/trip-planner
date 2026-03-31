"""Canonical adapter interface for fetching raw source snapshots."""

from __future__ import annotations

from abc import ABC, abstractmethod

from trip_planner.sources.models import SourceRecord
from trip_planner.sources.snapshots import NormalizationHandoff, RawSnapshot, SourceQuery


class SourceAdapter(ABC):
    """Stable boundary for source-specific connectors.

    Adapters own provider-specific payload fetching. Downstream planning code
    consumes `RawSnapshot` and `NormalizationHandoff` instead of reading
    transport- or provider-specific envelopes directly.
    """

    adapter_id: str
    source_record: SourceRecord
    supported_entity_scopes: tuple[str, ...]
    supported_option_kinds: tuple[str, ...]
    capabilities: tuple[str, ...]

    @abstractmethod
    def fetch_snapshot(self, query: SourceQuery) -> RawSnapshot:
        """Fetch or read a raw provider snapshot for the requested scope."""

    @abstractmethod
    def build_handoff(self, snapshot: RawSnapshot) -> NormalizationHandoff:
        """Describe the normalized handoff boundary for downstream pipelines."""
