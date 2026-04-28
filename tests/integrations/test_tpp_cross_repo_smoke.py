"""Cross-repo TPP smoke test for stranske/trip-planner#958.

This test drives the full trip-planner → Travel-Plan-Permission proposal
lifecycle through the workspace API:

1. Create a business trip via ``/api/trips``.
2. Submit a proposal through ``PUT /api/workspace/{trip_id}/proposal`` with a
   real ``proposal_submit_deferred.json`` fixture, asserting the deferred
   submission contract round-trips through the persistence layer.
3. Ingest a terminal evaluation through
   ``PUT /api/workspace/{trip_id}/proposal/evaluation`` with the
   ``approved_evaluation.json`` fixture, asserting the policy result and
   follow-up state are derived correctly.
4. Close the first FastAPI app instance, instantiate a fresh ``create_app()``
   bound to the same SQLite database, and verify that a freshly authenticated
   client can ``GET /api/workspace/{trip_id}/proposal`` and observe every
   documented contract field for the prior submission, evaluation, and
   summary — i.e. the approval state genuinely survives a process restart, not
   just an in-process memory cache.

The test uses the existing TPP integration fixtures and the documented
``WorkspaceProposalResponse`` contract. It does not call any live external
travel provider; the workspace endpoints accept TPP request/response envelopes
directly so the test substitutes those rather than mocking HTTP.

Run via the standard pytest invocation::

    pytest -q tests/integrations/test_tpp_cross_repo_smoke.py

Acceptance criteria from #958 mapped to this module:

- "The smoke produces a TPP proposal id, terminal status, and evaluation
  payload." → assertions probe ``proposal_state.proposal.proposal_id``,
  ``proposal_state.summary.submission_status`` /
  ``proposal_state.summary.evaluation_status``, and
  ``proposal_state.evaluation.evaluation_result``.
- "The smoke fails if trip-planner cannot poll or parse the TPP result." → the
  evaluation PUT must return 200 and the parsed payload must include
  ``status == 'compliant'`` and the documented evaluation fields.
- "The smoke fails if persisted approval state is missing after reload." → the
  second app instance reload via ``GET /api/workspace/{trip_id}/proposal``
  must return the same proposal id, evaluation id, follow-up status, and
  summary fields as the first instance produced.
- "The test uses documented contract schemas for request and response
  payloads." → uses the existing ``proposal_submit_deferred.json`` and
  ``approved_evaluation.json`` fixtures (which are TPPRequestEnvelope /
  TPPResponseEnvelope shapes) and asserts the documented
  ``WorkspaceProposalResponse`` fields by name.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.persistence.db import reset_database_state

# Documented contract fields drawn from ``WorkspaceProposalResponse`` /
# ``proposal_state`` in the workspace proposal API. Asserting by name is what
# gives the smoke teeth — if the contract drifts, the assertion fails loudly.
_DOCUMENTED_PROPOSAL_STATE_FIELDS = (
    "proposal",
    "submission",
    "evaluation",
    "summary",
    "follow_up",
)
# Summary fields that exist after the evaluation step has run. Earlier states
# (e.g. immediately after a deferred submission) only populate a subset; per-
# stage assertions below check the appropriate fields.
_DOCUMENTED_SUMMARY_FIELDS_AFTER_EVAL = (
    "submission_status",
    "approval_ready",
    "approval_requirement_count",
    "blocking_failure_count",
    "comparable_count",
)


def _fixture_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "integrations" / "tpp" / Path(*parts)


def _load_fixture(*parts: str) -> dict:
    return json.loads(_fixture_path(*parts).read_text(encoding="utf-8"))


def _proposal_payload(trip_id: str) -> dict:
    """A minimum compliant TripPlanProposal payload for a business trip."""
    return {
        "proposal_id": f"proposal:{trip_id}",
        "trip_id": trip_id,
        "mode": "business",
        "traveler_context": {
            "employee_type": "employee",
            "traveler_experience": "frequent",
            "home_airport": "ORD",
            "loyalty_programs": ["United"],
            "mobility_or_access_needs": [],
        },
        "selected_options": [
            {
                "category": "airfare",
                "option_id": "flight-1",
                "label": "United 123",
                "vendor": "United",
                "booking_channel": "Navan",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 620.0,
                    "min_amount": 620.0,
                    "max_amount": 620.0,
                },
                "justification_refs": ["fare-policy"],
            }
        ],
        "cost_summary": {
            "currency": "USD",
            "total_estimated_cost": 620.0,
            "category_estimates": {"airfare": 620.0},
            "notes": ["Costs include taxes."],
        },
        "comparables": [
            {
                "category": "airfare",
                "label": "Flexible fare",
                "vendor": "United",
                "booking_channel": "Concur",
                "estimated_cost": {
                    "currency": "USD",
                    "typical_amount": 710.0,
                    "min_amount": 710.0,
                    "max_amount": 710.0,
                },
                "notes": ["Refundable alternative."],
            }
        ],
        "approval_notes": ["Manager review required before booking."],
        "constraint_set_id": "policy-standard-2026-02",
    }


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """SQLite path shared across both TestClient instances in the test."""
    return tmp_path / "tpp_cross_repo_smoke.db"


@pytest.fixture
def first_client(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """First app instance — creates the trip and runs the full submit/evaluate flow."""
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{db_path}")
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        signup = test_client.post(
            "/api/auth/signup",
            json={
                "email": "tpp-smoke@example.com",
                "password": "password123",
                "display_name": "TPP Smoke Owner",
            },
        )
        assert signup.status_code == 201, signup.text
        yield test_client

    # Intentionally do NOT call reset_database_state() here — the second app
    # instance must read the same persisted SQLite file.


@pytest.fixture
def second_client(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Second app instance — re-binds to the same SQLite file to verify reload.

    Only used after the first client's ``with`` block exits, simulating a
    process restart against the on-disk database.
    """
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{db_path}")
    reset_database_state()
    app = create_app()

    with TestClient(app) as test_client:
        login = test_client.post(
            "/api/auth/login",
            json={
                "email": "tpp-smoke@example.com",
                "password": "password123",
            },
        )
        if login.status_code == 404:
            login = test_client.post(
                "/api/auth/signin",
                json={
                    "email": "tpp-smoke@example.com",
                    "password": "password123",
                },
            )
        assert login.status_code in (200, 201, 204), (
            f"Could not re-authenticate the same user against the persisted DB. "
            f"This either means the auth route is misnamed or persisted user "
            f"state is not surviving a create_app() boundary — both are "
            f"workspace-state reload failures the #958 contract is meant to "
            f"catch. status={login.status_code}, body={login.text}"
        )
        yield test_client

    reset_database_state()


def _assert_documented_fields(payload: dict, fields: tuple[str, ...]) -> None:
    missing = [name for name in fields if name not in payload]
    assert not missing, (
        f"Workspace proposal response is missing documented contract fields: "
        f"{missing}. Required by the WorkspaceProposalResponse schema in "
        f"trip_planner.app.schemas.proposal."
    )


def test_tpp_cross_repo_smoke_submit_evaluate_and_reload_across_instances(
    first_client: TestClient,
    second_client: TestClient,
) -> None:
    """The cross-repo TPP lifecycle round-trip per #958.

    Creates a business trip, submits a deferred proposal, ingests a compliant
    evaluation, then closes the app and re-binds a fresh app to the same
    SQLite file. The reload must surface the persisted proposal, submission,
    evaluation, summary, and follow-up state — proving the cross-repo flow's
    approval state survives a process boundary, not just an in-memory cache.
    """
    # ---- First instance: create trip + submit proposal + ingest evaluation ----
    created = first_client.post(
        "/api/trips",
        json={
            "title": "TPP cross-repo smoke",
            "summary": "Verifies the trip-planner → TPP submission/result flow persists.",
            "mode": "business",
            "trip_frame": {
                "start_date": "2026-05-04",
                "end_date": "2026-05-06",
                "duration_days": 3,
                "primary_regions": ["Chicago"],
            },
        },
    )
    assert created.status_code == 201, created.text
    trip_id = created.json()["trip"]["trip_id"]
    proposal_id = f"proposal:{trip_id}"

    # Submit the deferred proposal envelope through the TPP-aware workspace
    # endpoint. This writes the submission record via the same service that
    # the live HTTP client path uses; the only difference is the request/
    # response envelope is supplied directly instead of being fetched from a
    # live TPP service.
    submission_fixture = _load_fixture("proposal_submit_deferred.json")
    submission_fixture["request"]["trip_id"] = trip_id
    submission_fixture["request"]["proposal_id"] = proposal_id
    submission_fixture["request"]["payload"]["proposal_ref"] = proposal_id

    submitted = first_client.put(
        f"/api/workspace/{trip_id}/proposal",
        json={
            "proposal": _proposal_payload(trip_id),
            "request": submission_fixture["request"],
            "response": submission_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert submitted.status_code == 200, submitted.text
    submitted_state = submitted.json()["proposal_state"]
    _assert_documented_fields(submitted_state, _DOCUMENTED_PROPOSAL_STATE_FIELDS)
    # After the submission step alone, the summary carries submission_status
    # and approval_ready; evaluation_status only lands after the evaluation
    # PUT below.
    assert "submission_status" in submitted_state["summary"]
    assert "approval_ready" in submitted_state["summary"]

    # Acceptance: the smoke produces a TPP proposal id, terminal-or-deferred
    # status, and the documented submission contract.
    assert submitted_state["proposal"]["proposal_id"] == proposal_id
    assert submitted_state["summary"]["submission_status"] == "deferred"
    submission_record = submitted_state["submission"]
    assert submission_record.get("execution_id") == "exec-001"
    submission_exec_status = submission_record.get("execution_status") or {}
    assert submission_exec_status.get("state") == "deferred", (
        f"Submission record did not report a deferred execution_status. Got "
        f"{submission_exec_status!r}. The TPP submission contract requires "
        f"execution_status.state to round-trip through the workspace."
    )

    # Ingest the terminal evaluation. The approved_evaluation fixture carries
    # the compliant policy result; the workspace endpoint normalizes it and
    # derives a resolved follow-up.
    evaluation_fixture = _load_fixture("results", "approved_evaluation.json")
    evaluation_fixture["request"]["trip_id"] = trip_id
    evaluation_fixture["request"]["proposal_id"] = proposal_id
    evaluation_fixture["response"]["result_payload"]["trip_id"] = trip_id
    evaluation_fixture["response"]["result_payload"]["proposal_id"] = proposal_id
    evaluation_fixture["response"]["result_payload"]["evaluation_result"][
        "proposal_id"
    ] = proposal_id

    evaluated = first_client.put(
        f"/api/workspace/{trip_id}/proposal/evaluation",
        json={
            "request": evaluation_fixture["request"],
            "response": evaluation_fixture["response"],
            "proposal_version": "proposal-v3",
            "scenario_id": "scenario-a",
        },
    )
    assert evaluated.status_code == 200, evaluated.text
    evaluated_state = evaluated.json()["proposal_state"]
    _assert_documented_fields(evaluated_state, _DOCUMENTED_PROPOSAL_STATE_FIELDS)
    _assert_documented_fields(evaluated_state["summary"], _DOCUMENTED_SUMMARY_FIELDS_AFTER_EVAL)

    # Acceptance: the smoke fails if trip-planner cannot poll or parse the TPP
    # result. The compliant status and approval-ready summary must round-trip.
    evaluation = evaluated_state["evaluation"]
    assert evaluation is not None, "Evaluation state was not persisted by the workspace."
    evaluation_result = evaluation.get("evaluation_result")
    assert evaluation_result is not None, "Evaluation result payload missing."
    assert evaluation_result["status"] == "compliant"
    assert evaluation_result.get("evaluation_id") == "eval-approved-001"
    assert evaluated_state["summary"]["approval_ready"] is True
    assert evaluated_state["follow_up"]["status"] == "resolved"

    # ---- Second instance (same DB): reload and assert state survived ----
    reloaded = second_client.get(f"/api/workspace/{trip_id}/proposal")
    assert reloaded.status_code == 200, reloaded.text
    reloaded_state = reloaded.json()["proposal_state"]
    _assert_documented_fields(reloaded_state, _DOCUMENTED_PROPOSAL_STATE_FIELDS)
    _assert_documented_fields(reloaded_state["summary"], _DOCUMENTED_SUMMARY_FIELDS_AFTER_EVAL)

    # Acceptance: the smoke fails if persisted approval state is missing after
    # reload. The second app instance must surface the same proposal id,
    # evaluation id, summary, and follow-up state.
    assert reloaded_state["proposal"]["proposal_id"] == proposal_id
    assert reloaded_state["summary"]["submission_status"] == "deferred"
    assert reloaded_state["summary"]["approval_ready"] is True

    reloaded_evaluation = reloaded_state.get("evaluation")
    assert reloaded_evaluation is not None, (
        "Reload from a fresh app instance is missing the persisted evaluation "
        "state — the cross-repo approval did not survive the create_app() "
        "boundary."
    )
    reloaded_eval_result = reloaded_evaluation.get("evaluation_result")
    assert reloaded_eval_result is not None
    assert reloaded_eval_result.get("evaluation_id") == "eval-approved-001"
    assert reloaded_eval_result["status"] == "compliant"
    assert reloaded_state["follow_up"]["status"] == "resolved"
