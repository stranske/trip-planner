"""Capture lodging deep links without live OTA search."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from trip_planner._validators import require_non_empty, require_optional_non_empty
from trip_planner.sources.models import SourceRecord
from trip_planner.sources.provenance import ProvenanceReference
from trip_planner.sources.snapshots import (
    NormalizationHandoff,
    RawSnapshot,
    RawSourceRecord,
    SourceQuery,
)

from .base import SourceAdapter

_DEEP_LINK_FILTER_KEY = "deep_link"
_TARGET_CONTRACT = "trip_planner/contracts/lodging.py"


@dataclass(slots=True)
class LodgingDeepLinkCapture:
    """Traveler-supplied lodging deep link captured for later normalization."""

    deep_link: str
    captured_at: str = ""
    provider_label: str = ""
    listing_title: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.deep_link, "deep_link")
        parsed = urlparse(self.deep_link)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("deep_link must be an absolute http or https URL")
        require_optional_non_empty(self.captured_at or None, "captured_at")
        require_optional_non_empty(self.provider_label or None, "provider_label")
        require_optional_non_empty(self.listing_title or None, "listing_title")


class LodgingDeepLinkAdapter(SourceAdapter):
    """Store traveler-captured lodging deep links and seed provenance."""

    def __init__(self) -> None:
        self.adapter_id = "lodging-deep-link"
        self.source_record = SourceRecord(
            source_id="traveler-lodging-deep-link",
            provider_name="Traveler Capture",
            display_name="Traveler Lodging Deep Link",
            category="specialist_non_commercial",
            coverage_scope="global",
            supported_option_kinds=["lodging"],
            notes=[
                "Honest lodging lane that stores deep links without live OTA search."
            ],
        )
        self.supported_entity_scopes = ("lodging",)
        self.supported_option_kinds = ("lodging",)
        self.capabilities = ("read_capture", "supports_normalization_handoff")

    def capture(self, capture: LodgingDeepLinkCapture, query: SourceQuery) -> RawSnapshot:
        if query.entity_scope != "lodging":
            raise ValueError("query.entity_scope must be lodging")
        if query.option_kind != "lodging":
            raise ValueError("query.option_kind must be lodging")

        captured_at = capture.captured_at or query.requested_at or "1970-01-01T00:00:00Z"
        record_id = f"{query.query_id}-deep-link"
        record = RawSourceRecord(
            record_id=record_id,
            entity_scope="lodging",
            provider_entity_id=capture.deep_link,
            payload_type="deep_link_capture",
            payload={
                "deep_link": capture.deep_link,
                "provider_label": capture.provider_label,
                "listing_title": capture.listing_title,
            },
            captured_at=captured_at,
            payload_locator=capture.deep_link,
            provenance_hint="traveler_capture",
            metadata={"capture_mode": "deep_link"},
            notes=["Captured lodging deep link without live OTA search."],
        )
        return RawSnapshot(
            snapshot_id=f"{query.query_id}-snapshot",
            adapter_id=self.adapter_id,
            source_id=self.source_record.source_id,
            source_category=self.source_record.category,
            entity_scope="lodging",
            option_kind="lodging",
            fetched_at=captured_at,
            query=query,
            records=[record],
            transport="capture",
            snapshot_status="complete",
            handoff_status="ready",
            payload_metadata={"capture_mode": "deep_link"},
            notes=["Lodging deep-link capture snapshot ready for normalization."],
        )

    def fetch_snapshot(self, query: SourceQuery) -> RawSnapshot:
        deep_link = query.filters.get(_DEEP_LINK_FILTER_KEY, "")
        if not deep_link:
            raise ValueError(f"query.filters must include {_DEEP_LINK_FILTER_KEY!r}")
        return self.capture(
            LodgingDeepLinkCapture(
                deep_link=deep_link,
                captured_at=query.requested_at,
                provider_label=query.filters.get("provider_label", ""),
                listing_title=query.filters.get("listing_title", ""),
            ),
            query,
        )

    def build_handoff(self, snapshot: RawSnapshot) -> NormalizationHandoff:
        provenance_refs = [
            ProvenanceReference(
                provenance_id=f"{snapshot.snapshot_id}:{record.record_id}",
                source_id=snapshot.source_id,
                source_category=snapshot.source_category,
                subject_kind="option",
                subject_id=f"{record.record_id}:lodging-candidate",
                contribution_kind="editorial",
                summary="Seeded provenance from a traveler-captured lodging deep link.",
                locator=record.payload_locator or record.payload["deep_link"],
                captured_at=record.captured_at or snapshot.fetched_at,
                notes=["Attach this reference to the eventual LodgingOption source_refs list."],
            )
            for record in snapshot.records
        ]
        return NormalizationHandoff(
            handoff_id=f"{snapshot.snapshot_id}-handoff",
            snapshot_id=snapshot.snapshot_id,
            target_contract=_TARGET_CONTRACT,
            entity_scope=snapshot.entity_scope,
            status="ready",
            input_record_ids=[record.record_id for record in snapshot.records],
            provenance_refs=provenance_refs,
            record_count=len(snapshot.records),
            notes=["Normalization can start from the captured deep-link snapshot."],
        )
