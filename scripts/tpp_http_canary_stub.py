#!/usr/bin/env python3
"""Deterministic local HTTP TPP double for browser canary runs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

CANARY_ACCESS_TOKEN = "canary-tpp-access-token"
CANARY_EXECUTION_ID = "exec-canary-approval-packet"
GENERATED_AT = "2026-11-16T12:00:00Z"


class TppCanaryStubHandler(BaseHTTPRequestHandler):
    server_version = "TppCanaryStub/1.0"

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _authorized(self) -> bool:
        return self.headers.get("Authorization", "") == f"Bearer {CANARY_ACCESS_TOKEN}"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _unauthorized(self) -> None:
        self._send_json(401, {"detail": "Unauthorized"})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/readyz":
            self._send_json(200, {"status": "ready"})
            return
        if not self._authorized():
            self._unauthorized()
            return
        body = self._read_json_body()
        if self.path.startswith("/api/planner/policy-snapshot"):
            self._send_json(200, self._policy_snapshot())
            return
        poll = re.fullmatch(
            r"/api/planner/proposals/(?P<proposal>[^/]+)/executions/(?P<execution>[^/]+)",
            self.path,
        )
        if poll:
            self._send_json(
                200,
                self._poll_response(proposal_id=poll.group("proposal"), execution_id=poll.group("execution")),
            )
            return
        evaluation = re.fullmatch(
            r"/api/planner/executions/(?P<execution>[^/]+)/evaluation-result",
            self.path,
        )
        if evaluation:
            self._send_json(200, self._evaluation_response(body, execution_id=evaluation.group("execution")))
            return
        self._send_json(404, {"detail": f"Unknown path {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._unauthorized()
            return
        body = self._read_json_body()
        if self.path == "/api/planner/proposals":
            self._send_json(200, self._submit_response(body))
            return
        self._send_json(404, {"detail": f"Unknown path {self.path}"})

    @staticmethod
    def _policy_snapshot() -> dict[str, Any]:
        return {
            "trip_id": "placeholder",
            "freshness": "current",
            "generated_at": GENERATED_AT,
            "expires_at": "2026-11-17T12:00:00Z",
            "invalidated_at": None,
            "invalidation_reason": None,
            "policy_status": "pass",
            "booking_requirements": [],
            "documentation_rules": [],
            "approval_triggers": [],
            "airfare_rules": {"max_cabin": "economy"},
            "lodging_rules": {},
            "ground_transport_rules": {},
            "meal_rules": {},
            "budget_rules": {},
            "comparable_requirements": {},
            "versioning": {
                "contract_version": "2026-04-11",
                "policy_version": "canary-policy-v1",
                "planner_known_policy_version": None,
                "compatible_with_planner_cache": True,
                "etag": "canary:policy:v1",
            },
        }

    def _submit_response(self, body: dict[str, Any]) -> dict[str, Any]:
        request = body.get("request") if isinstance(body.get("request"), dict) else {}
        trip_id = str(request.get("trip_id") or body.get("trip_plan", {}).get("trip_id") or "trip-unknown")
        proposal_id = str(request.get("proposal_id") or f"proposal:{trip_id}")
        base_url = f"http://{self.server.server_address[0]}:{self.server.server_address[1]}"
        status_endpoint = (
            f"{base_url}/api/planner/proposals/{proposal_id}/executions/{CANARY_EXECUTION_ID}"
        )
        return {
            "operation": "submit_proposal",
            "submission_status": "submitted",
            "request_id": "canary-submit",
            "correlation_id": {"value": "canary", "issued_by": "tpp"},
            "transport_pattern": "deferred",
            "execution_status": {
                "state": "deferred",
                "terminal": False,
                "summary": "Proposal queued for evaluation",
                "poll_after_seconds": 0,
                "external_status": "202 Accepted",
                "updated_at": GENERATED_AT,
            },
            "result_payload": {
                "execution_id": CANARY_EXECUTION_ID,
                "queue_state": "waiting_for_policy_engine",
                "trip_id": trip_id,
                "proposal_id": proposal_id,
            },
            "received_at": GENERATED_AT,
            "status_endpoint": status_endpoint,
        }

    def _poll_response(self, *, proposal_id: str, execution_id: str) -> dict[str, Any]:
        base_url = f"http://{self.server.server_address[0]}:{self.server.server_address[1]}"
        return {
            "operation": "poll_execution_status",
            "transport_pattern": "deferred",
            "execution_status": {
                "state": "deferred",
                "terminal": False,
                "summary": "Awaiting evaluator completion",
                "updated_at": GENERATED_AT,
            },
            "result_payload": {
                "execution_id": execution_id,
                "proposal_id": proposal_id,
                "queue_state": "waiting_for_policy_engine",
            },
            "received_at": GENERATED_AT,
            "status_endpoint": (
                f"{base_url}/api/planner/proposals/{proposal_id}/executions/{execution_id}"
            ),
        }

    def _evaluation_response(self, body: dict[str, Any], *, execution_id: str) -> dict[str, Any]:
        request = body if isinstance(body, dict) else {}
        trip_id = str(request.get("trip_id") or "trip-unknown")
        proposal_id = str(request.get("proposal_id") or f"proposal:{trip_id}")
        proposal_version = str(request.get("proposal_version") or "proposal-v3")
        base_url = f"http://{self.server.server_address[0]}:{self.server.server_address[1]}"
        return {
            "trip_id": trip_id,
            "proposal_id": proposal_id,
            "proposal_version": proposal_version,
            "execution_id": execution_id,
            "request_id": "canary-eval",
            "correlation_id": {"value": "canary", "issued_by": "tpp"},
            "outcome": "compliant",
            "result_endpoint": f"GET /api/planner/executions/{execution_id}/evaluation-result",
            "status_endpoint": (
                f"{base_url}/api/planner/proposals/{proposal_id}/executions/{execution_id}"
            ),
            "policy_result": {
                "status": "pass",
                "issues": [],
                "policy_version": "canary-policy-v1",
            },
            "blocking_issues": [],
            "preferred_alternatives": [],
            "exception_requirements": [],
            "reoptimization_guidance": [],
            "generated_at": GENERATED_AT,
        }

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), TppCanaryStubHandler)
    host, port = server.server_address
    print(f"TPP canary stub listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())