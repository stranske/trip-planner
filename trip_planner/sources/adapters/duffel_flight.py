"""Read Duffel test-mode flight offers into the canonical source boundary."""

from __future__ import annotations

import hashlib
import http.client
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from trip_planner.sources.models import SourceRecord
from trip_planner.sources.provenance import ProvenanceReference
from trip_planner.sources.snapshots import (
    AdapterIssue,
    NormalizationHandoff,
    RawSnapshot,
    RawSourceRecord,
    SourceQuery,
)

from .base import SourceAdapter

_API_BASE_URL = "https://api.duffel.com"
_TARGET_CONTRACT = "trip_planner/options/transport.py"
_CABIN_CLASSES = {"economy", "premium_economy", "business", "first"}

JsonTransport = Callable[[Request, float], bytes]


def _default_transport(request: Request, timeout: float) -> bytes:
    """Send one Duffel request and return its response body."""

    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _decode_object(raw: bytes, source: str) -> dict[str, Any]:
    """Decode a JSON object with a provider-specific validation message."""

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Duffel {source} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"Duffel {source} must contain a JSON object")
    return payload


def _required_text(payload: dict[str, Any], field: str, context: str) -> str:
    """Return one required non-empty string from a provider payload."""

    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Duffel {context} requires non-empty string field {field!r}")
    return value.strip()


def _iata_code(value: str, field: str) -> str:
    """Validate a Duffel airport or city IATA code."""

    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError(f"query.{field} must be a three-letter IATA code")
    return normalized


class DuffelFlightAdapter(SourceAdapter):
    """Fetch Duffel test-mode offers or replay a recorded response fixture.

    A token is deliberately accepted only when it has Duffel's documented
    ``duffel_test_`` prefix. CI passes ``fixture_path`` instead, so tests never
    depend on provider availability or credentials.
    """

    def __init__(
        self,
        *,
        api_token: str | None = None,
        fixture_path: str | Path | None = None,
        api_base_url: str = _API_BASE_URL,
        timeout: float = 25.0,
        transport: JsonTransport = _default_transport,
    ) -> None:
        if api_token is None and fixture_path is None:
            raise ValueError("api_token or fixture_path is required")
        if api_token is not None and not api_token.startswith("duffel_test_"):
            raise ValueError("api_token must be a Duffel test-mode token")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.api_token = api_token
        self.fixture_path = Path(fixture_path) if fixture_path is not None else None
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport
        self.adapter_id = "duffel-flight-test-mode"
        self.source_record = SourceRecord(
            source_id="duffel-flight-offers",
            provider_name="Duffel",
            display_name="Duffel Flight Offers",
            category="commercial_inventory",
            coverage_scope="global",
            supported_option_kinds=["flight"],
            base_url="https://duffel.com/",
            notes=["Test-mode offers are non-bookable production inventory evidence."],
        )
        self.supported_entity_scopes = ("transport",)
        self.supported_option_kinds = ("flight",)
        self.capabilities = (
            "fetch_live" if api_token is not None else "read_fixture",
            "supports_normalization_handoff",
        )

    def _request_payload(self, query: SourceQuery) -> dict[str, Any]:
        """Build the documented Duffel v2 offer-request envelope."""

        if query.entity_scope != "transport":
            raise ValueError("query.entity_scope must be transport")
        if query.option_kind != "flight":
            raise ValueError("query.option_kind must be flight")
        if not query.requested_at:
            raise ValueError("query.requested_at is required")

        origin = _iata_code(query.origin, "origin")
        destination = _iata_code(query.destination, "destination")
        departure_date = query.filters.get("departure_date", "")
        try:
            date.fromisoformat(departure_date)
        except ValueError as exc:
            raise ValueError("query.filters['departure_date'] must be an ISO date") from exc

        cabin_class = query.filters.get("cabin_class", "economy")
        if cabin_class not in _CABIN_CLASSES:
            raise ValueError(f"cabin_class must be one of {sorted(_CABIN_CLASSES)!r}")

        return {
            "data": {
                "cabin_class": cabin_class,
                "slices": [
                    {
                        "origin": origin,
                        "destination": destination,
                        "departure_date": departure_date,
                    }
                ],
                "passengers": [{"type": query.filters.get("passenger_type", "adult")}],
            }
        }

    def _load_fixture(self) -> dict[str, Any]:
        """Load the configured recorded Duffel response."""

        assert self.fixture_path is not None
        if not self.fixture_path.is_file():
            raise ValueError(f"Duffel fixture does not exist: {self.fixture_path}")
        return _decode_object(self.fixture_path.read_bytes(), "fixture")

    def _fetch_live(self, query: SourceQuery) -> tuple[dict[str, Any] | None, AdapterIssue | None]:
        """Fetch one Duffel test-mode response, preserving provider failures."""

        endpoint = f"{self.api_base_url}/air/offer_requests?supplier_timeout=10000"
        request = Request(
            endpoint,
            data=json.dumps(self._request_payload(query)).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Duffel-Version": "v2",
                "Authorization": f"Bearer {self.api_token}",
            },
            method="POST",
        )
        try:
            raw = self.transport(request, self.timeout)
        except HTTPError as exc:
            return None, self._provider_issue(
                query,
                code="duffel_http_error",
                message=f"Duffel returned HTTP {exc.code}",
                provider_status=str(exc.code),
                retriable=exc.code >= 500 or exc.code == 429,
            )
        except (OSError, http.client.HTTPException) as exc:
            return None, self._provider_issue(
                query,
                code="duffel_unavailable",
                message=f"Duffel request failed: {exc}",
                retriable=True,
            )
        try:
            return _decode_object(raw, "response"), None
        except (TypeError, ValueError) as exc:
            return None, self._provider_issue(
                query,
                code="duffel_invalid_json",
                message=str(exc),
                retriable=False,
                stage="decode",
            )

    def _failed_snapshot(self, query: SourceQuery, issue: AdapterIssue) -> RawSnapshot:
        """Return the canonical blocked snapshot for an API failure."""

        return RawSnapshot(
            snapshot_id=f"{query.query_id}-snapshot",
            adapter_id=self.adapter_id,
            source_id=self.source_record.source_id,
            source_category=self.source_record.category,
            entity_scope="transport",
            option_kind="flight",
            fetched_at=query.requested_at,
            query=query,
            issues=[issue],
            transport="api",
            snapshot_status="failed",
            handoff_status="blocked",
            payload_metadata={"mode": "test-api"},
            notes=["Duffel request failed; no offer records were emitted."],
        )

    def _provider_issue(
        self,
        query: SourceQuery,
        *,
        code: str,
        message: str,
        provider_status: str = "",
        retriable: bool,
        stage: str = "fetch",
    ) -> AdapterIssue:
        """Build a canonical issue for one failed provider request."""

        return AdapterIssue(
            issue_id=f"{query.query_id}-{code}",
            stage=stage,
            severity="error",
            code=code,
            message=message,
            observed_at=query.requested_at,
            provider_status=provider_status,
            retriable=retriable,
        )

    def _records_from_payload(
        self, payload: dict[str, Any], query: SourceQuery, *, locator_prefix: str
    ) -> tuple[list[RawSourceRecord], dict[str, Any]]:
        """Validate a Duffel response envelope and convert its offers."""

        data = payload.get("data")
        if not isinstance(data, dict):
            raise TypeError("Duffel response requires an object field 'data'")
        offers = data.get("offers")
        if not isinstance(offers, list):
            raise TypeError("Duffel response data requires an offers list")

        records: list[RawSourceRecord] = []
        for index, offer in enumerate(offers):
            if not isinstance(offer, dict):
                raise TypeError(f"Duffel offer at index {index} must be an object")
            offer_id = _required_text(offer, "id", f"offer at index {index}")
            total_amount = _required_text(offer, "total_amount", f"offer {offer_id!r}")
            total_currency = _required_text(offer, "total_currency", f"offer {offer_id!r}")
            expires_at = _required_text(offer, "expires_at", f"offer {offer_id!r}")
            slices = offer.get("slices")
            if not isinstance(slices, list) or not slices:
                raise ValueError(f"Duffel offer {offer_id!r} requires a non-empty slices list")

            owner = offer.get("owner")
            owner_id = ""
            if isinstance(owner, dict):
                raw_owner_id = owner.get("id")
                if isinstance(raw_owner_id, str):
                    owner_id = raw_owner_id

            canonical = json.dumps(offer, sort_keys=True, separators=(",", ":")).encode("utf-8")
            records.append(
                RawSourceRecord(
                    record_id=f"{query.query_id}-offer-{offer_id}",
                    entity_scope="transport",
                    provider_entity_id=offer_id,
                    payload_type="duffel_flight_offer",
                    payload=offer,
                    content_language=query.locale,
                    captured_at=query.requested_at,
                    payload_locator=f"{locator_prefix}#{offer_id}",
                    payload_checksum=hashlib.sha256(canonical).hexdigest(),
                    provenance_hint="commercial_flight_inventory",
                    metadata={
                        "total_amount": total_amount,
                        "total_currency": total_currency,
                        "expires_at": expires_at,
                        "owner_id": owner_id,
                    },
                    notes=["Test-mode offer; availability and price are not production quotes."],
                )
            )
        return records, data

    def fetch_snapshot(self, query: SourceQuery) -> RawSnapshot:
        """Fetch test-mode offers or load the recorded offline response."""

        self._request_payload(query)
        mode = "api" if self.api_token is not None else "fixture"
        if self.api_token is not None:
            payload, issue = self._fetch_live(query)
            if issue is not None:
                return self._failed_snapshot(query, issue)
            assert payload is not None
            locator_prefix = f"{self.api_base_url}/air/offers"
        else:
            payload = self._load_fixture()
            assert self.fixture_path is not None
            locator_prefix = self.fixture_path.name

        try:
            records, data = self._records_from_payload(
                payload, query, locator_prefix=locator_prefix
            )
            request_id = _required_text(data, "id", "offer request")
            if data.get("live_mode") is not False:
                raise ValueError("Duffel response must come from test mode (live_mode=false)")
        except (TypeError, ValueError) as exc:
            if mode != "api":
                raise
            return self._failed_snapshot(
                query,
                self._provider_issue(
                    query,
                    code="duffel_invalid_response",
                    message=str(exc),
                    retriable=False,
                    stage="decode",
                ),
            )

        return RawSnapshot(
            snapshot_id=f"{query.query_id}-snapshot",
            adapter_id=self.adapter_id,
            source_id=self.source_record.source_id,
            source_category=self.source_record.category,
            entity_scope="transport",
            option_kind="flight",
            fetched_at=query.requested_at,
            query=query,
            records=records,
            payload_format="json",
            transport=mode,
            snapshot_status="complete",
            handoff_status="ready",
            payload_metadata={
                "mode": "test-api" if mode == "api" else "recorded-fixture",
                "offer_request_id": request_id,
                "offer_count": str(len(records)),
                "live_mode": "false",
            },
            notes=[f"Loaded Duffel test-mode offers from {mode}."],
        )

    def build_handoff(self, snapshot: RawSnapshot) -> NormalizationHandoff:
        """Describe the flight-option normalization boundary."""

        provenance_refs = [
            ProvenanceReference(
                provenance_id=f"{snapshot.snapshot_id}:{record.record_id}",
                source_id=snapshot.source_id,
                source_category=snapshot.source_category,
                subject_kind="option",
                subject_id=f"{record.record_id}:flight-option",
                contribution_kind="inventory",
                summary="Duffel test-mode offer supplied flight inventory and price evidence.",
                locator=record.payload_locator,
                captured_at=record.captured_at or snapshot.fetched_at,
                notes=["Reconfirm against live inventory before booking."],
            )
            for record in snapshot.records
        ]
        blocked = snapshot.snapshot_status == "failed"
        return NormalizationHandoff(
            handoff_id=f"{snapshot.snapshot_id}-handoff",
            snapshot_id=snapshot.snapshot_id,
            target_contract=_TARGET_CONTRACT,
            entity_scope=snapshot.entity_scope,
            status="blocked" if blocked else "ready",
            input_record_ids=[record.record_id for record in snapshot.records],
            blocked_issue_ids=[issue.issue_id for issue in snapshot.issues],
            provenance_refs=provenance_refs,
            record_count=len(snapshot.records),
            notes=[
                (
                    "Duffel request failed; normalization is blocked."
                    if blocked
                    else "Flight offers are ready for transport-option normalization."
                )
            ],
        )
