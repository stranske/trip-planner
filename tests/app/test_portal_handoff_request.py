"""Enforce the empty JSON request boundary for browser handoff preparation."""

from urllib.parse import urlencode

import pytest
from fastapi import HTTPException, Request
from fastapi.routing import APIRoute

from trip_planner.app.routes.proposal import _require_json_handoff, router


def _request(query: dict[str, str], content_type: str = "application/json") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/workspace/trip-1/proposal/handoff",
            "query_string": urlencode(query).encode("ascii"),
            "headers": [(b"content-type", content_type.encode("ascii"))],
        }
    )


@pytest.mark.parametrize(
    "query",
    [
        {"action_url": "https://caller.example/portal/handoff"},
        {"fields": '{"traveler_name":"Caller"}'},
        {"traveler_name": "Caller José & another traveler"},
        {"source_snapshot_hash": "sha256:" + "0" * 64},
    ],
    ids=["destination", "fields", "traveler-fact", "snapshot-binding"],
)
@pytest.mark.parametrize("suffix", ["/handoff", "/handoff/status"])
def test_handoff_routes_reject_query_overrides(query: dict[str, str], suffix: str) -> None:
    # Exercise the dependency registered on both routes, before their service
    # functions can persist preparation or read a producer receipt.
    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute) and route.path.endswith(suffix)
    )
    guard = next(
        dependency.call
        for dependency in route.dependant.dependencies
        if dependency.call is _require_json_handoff
    )
    with pytest.raises(HTTPException) as rejected:
        guard(_request(query))

    assert rejected.value.status_code == 422
    assert rejected.value.detail == "Prepare the portal handoff without query parameters."


@pytest.mark.parametrize(
    "content_type", ["application/json", "application/json; charset=UTF-8", "APPLICATION/JSON"]
)
def test_handoff_accepts_json_without_query_parameters(content_type: str) -> None:
    _require_json_handoff(_request({}, content_type))


@pytest.mark.parametrize("content_type", ["application/x-www-form-urlencoded", "text/plain", ""])
def test_handoff_preparation_rejects_form_and_non_json_bodies(content_type: str) -> None:
    with pytest.raises(HTTPException) as rejected:
        _require_json_handoff(_request({}, content_type))

    assert rejected.value.status_code == 415
