"""Truthful browser handoff into Travel-Plan-Permission's portal."""

from __future__ import annotations

import json
import os
from hashlib import sha256
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit, urlunsplit

PORTAL_HANDOFF_SCHEMA_VERSION = "tpp-portal-handoff/v1"


class TPPPortalHandoffConfigurationError(ValueError):
    """The configured portal origin cannot safely receive a browser handoff."""


def snapshot_hash(snapshot: dict[str, Any]) -> str:
    """Return a deterministic identity for the facts bound to a saved verdict."""

    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{sha256(encoded.encode('utf-8')).hexdigest()}"


def portal_action_url() -> str:
    """Resolve a fixed TPP portal action without accepting a caller-selected URL."""

    raw = (os.getenv("TPP_PORTAL_BASE_URL") or os.getenv("TPP_BASE_URL") or "").strip()
    if not raw:
        raise TPPPortalHandoffConfigurationError(
            "Travel-Plan-Permission portal handoff is not configured."
        )
    # Browsers treat backslashes as URL separators and strip embedded whitespace.
    # Reject those forms before parsing so the native form uses the same origin
    # that the server validated, rather than a browser-normalized alternative.
    if "\\" in raw or any(character.isspace() or ord(character) < 32 for character in raw):
        raise TPPPortalHandoffConfigurationError(
            "Travel-Plan-Permission portal handoff must be configured as an origin only."
        )
    try:
        parsed = urlsplit(raw)
        # Accessing port validates its syntax and range; urlsplit alone does not.
        _ = parsed.port
    except ValueError as error:
        raise TPPPortalHandoffConfigurationError(
            "Travel-Plan-Permission portal handoff must be configured as a valid origin."
        ) from error
    environment = os.getenv("TRIP_PLANNER_ENV", "local").strip().lower()
    local_environment = environment in {"local", "development", "dev", "test", "testing"}
    hostname = parsed.hostname or ""
    try:
        loopback = ip_address(hostname).is_loopback
    except ValueError:
        loopback = hostname.lower() == "localhost"
    allow_http = local_environment and loopback
    if parsed.scheme not in ({"http", "https"} if allow_http else {"https"}):
        raise TPPPortalHandoffConfigurationError(
            "Travel-Plan-Permission portal handoff requires an HTTPS origin."
        )
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise TPPPortalHandoffConfigurationError(
            "Travel-Plan-Permission portal handoff must be configured as an origin only."
        )
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")
    return f"{origin}/portal/handoff"


def _money(value: Any) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return f"{float(value):.2f}"


def _notes(snapshot: dict[str, Any]) -> str:
    lines = [
        "Prepared by trip-planner; complete and review all fields in Travel-Plan-Permission.",
        (
            "Workspace references: "
            f"trip={snapshot['trip_id']}; proposal={snapshot['proposal_id']}; "
            f"version={snapshot['proposal_version']}; scenario={snapshot.get('scenario_id') or 'none'}; "
            f"execution={snapshot.get('execution_id') or 'none'}."
        ),
    ]
    verdict = snapshot.get("verdict") or {}
    status = verdict.get("status") or "not recorded"
    outcome = verdict.get("outcome") or "not recorded"
    codes = ", ".join(verdict.get("blocking_codes") or []) or "none"
    lines.append(
        f"Saved trip-planner policy result: status={status}; outcome={outcome}; rule codes={codes}."
    )
    for row in snapshot.get("prices") or []:
        amount = _money(row.get("amount"))
        amount_text = f"{row.get('currency')} {amount}" if amount else "not priced"
        source = row.get("source") or {}
        attribution = source.get("attributed_to") or "not recorded"
        captured = source.get("captured_at") or "date not recorded"
        note = row.get("note") or "no source note"
        lines.append(
            f"Price {row.get('label') or row.get('component')}: {amount_text}; "
            f"{note}; entered by {attribution} on {captured}."
        )
    lines.append(
        "This prior policy result and these prices are context only; TPP recalculates policy "
        "from the completed portal draft."
    )
    return "\n".join(lines)


def _flight_fields(transport: dict[str, Any] | None) -> dict[str, str]:
    if not transport or not (
        any(
            transport.get(key) is not None
            for key in ("flight_amount", "lowest_amount", "cabin_class", "flight_hours")
        )
        or transport.get("evidence_attested") is True
    ):
        return {}

    fields: dict[str, str] = {}
    # ``transport.amount`` can combine flights, rail and car hire. It is not safe to
    # present that aggregate as an airfare merely because flight details accompany it.
    # A producer may populate ``flight_amount`` only when it owns a flight-specific
    # figure; until then the portal asks the traveller to complete the airfare fields.
    amount = _money(transport.get("flight_amount"))
    if amount:
        fields.update(
            {
                "flight_pref_outbound.roundtrip_cost": amount,
                "selected_fare": amount,
                "flight_cost": amount,
            }
        )
    lowest = _money(transport.get("lowest_amount"))
    if lowest:
        fields.update({"lowest_cost_roundtrip": lowest, "lowest_fare": lowest})
    if transport.get("cabin_class"):
        fields["cabin_class"] = str(transport["cabin_class"])
    if transport.get("flight_hours") is not None:
        fields["flight_duration_hours"] = str(transport["flight_hours"])
    if transport.get("evidence_attested") is not None:
        fields["fare_evidence_attached"] = "true" if transport["evidence_attested"] else "false"
    return fields


def build_portal_fields(snapshot: dict[str, Any]) -> dict[str, str]:
    """Map only facts TPP's portal contract accepts, without inventing missing values."""

    trip = snapshot.get("trip") or {}
    destinations = [str(value) for value in trip.get("primary_regions") or [] if value]
    fields: dict[str, str] = {
        "traveler_name": str(snapshot.get("traveler_name") or ""),
        "business_purpose": str(trip.get("summary") or trip.get("title") or ""),
        "city_state": ", ".join(destinations),
        "depart_date": str(trip.get("start_date") or ""),
        "return_date": str(trip.get("end_date") or ""),
        "notes": _notes(snapshot),
    }
    origin = str(trip.get("origin") or "").strip()
    if origin:
        fields["departure_city_airport"] = origin

    transport = next(
        (row for row in snapshot.get("prices") or [] if row.get("component") == "transport"),
        None,
    )
    # The transport row may combine rail, car and flights. Populate airfare-only fields only
    # when the traveller supplied flight-specific facts.
    fields.update(_flight_fields(transport))

    return {key: value for key, value in fields.items() if value != ""}
