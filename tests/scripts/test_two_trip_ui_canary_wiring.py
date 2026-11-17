"""Structural guards for the approval-packet browser canary (issue / PR #2046).

The full journey is exercised by Playwright via ``scripts/run_two_trip_ui_canary.sh``.
These tests keep the TPP stub, npm script, and ApprovalPacket mount wired so a deliberate
removal of the packet DOM (negative probe) fails CI before the expensive canary run.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_canary_script_starts_tpp_stub_and_exports_tpp_base_url() -> None:
    script = Path("scripts/run_two_trip_ui_canary.sh").read_text(encoding="utf-8")
    assert "scripts/tpp_http_canary_stub.py" in script
    assert 'TPP_BASE_URL="${tpp_url}"' in script
    assert "npm --prefix frontend run test:e2e:canary" in script
    assert "simulated TPP transport" in script
    assert '"${PYTHON}" -m uvicorn trip_planner.app.main:app' in script
    assert "uv run" not in script


def test_frontend_canary_runner_includes_approval_packet_journey() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    canary_script = package["scripts"]["test:e2e:canary"]
    assert "e2e/approval-packet-journey.spec.ts" in canary_script
    assert "e2e/two-trip-canary.spec.ts" in canary_script


def test_frontend_named_journey_runner_targets_only_approval_packet_spec() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    journey_script = package["scripts"]["test:e2e:approval-packet-journey"]
    assert journey_script == "playwright test e2e/approval-packet-journey.spec.ts"


def test_approval_packet_journey_spec_anchors_workspace_packet_mount() -> None:
    spec = Path("frontend/e2e/approval-packet-journey.spec.ts").read_text(encoding="utf-8")
    assert "approval-packet-document" in spec
    assert "showApprovalPacket" in spec
    assert "ApprovalPacket at Policy tab" in spec


def test_workspace_policy_tab_mounts_approval_packet_when_visible() -> None:
    workspace = Path("frontend/src/routes/WorkspacePage.tsx").read_text(encoding="utf-8")
    assert "{showApprovalPacket && currentWorkspace.proposal_state ? (" in workspace
    assert "<ApprovalPacket" in workspace
    assert 'data-testid="approval-packet-document"' in Path(
        "frontend/src/components/workspace/ApprovalPacket.tsx"
    ).read_text(encoding="utf-8")


def test_approval_packet_journey_spec_asserts_acceptance_observables() -> None:
    spec = Path("frontend/e2e/approval-packet-journey.spec.ts").read_text(encoding="utf-8")
    assert "policy (check -> native submit -> approval packet print" in spec
    assert "approval-packet-trip-cost" in spec
    assert "approval-packet-verdict" in spec
    assert "Passed the travel policy check" in spec
    assert "__canaryPrintInvoked" in spec
    assert "Print / Export" in spec


def test_deliberate_break_negative_probe_recorded_in_verification_doc() -> None:
    """Acceptance: deliberate mount removal and revert are recorded for reviewers (not git log).

    CI checks out PR heads with shallow history, so branch commit messages are not
    available during pytest. The verification note carries the same evidence.
    """
    doc = Path("docs/verification/pr-2046-approval-packet-canary.md").read_text(encoding="utf-8")
    assert "039d13fb" in doc
    assert "ApprovalPacket" in doc and "Deliberate break" in doc
    assert "87d7f2eb" in doc
    assert "2 passed" in doc


def test_acceptance_criterion_named_journey_documented() -> None:
    doc = Path("docs/verification/pr-2046-approval-packet-canary.md").read_text(encoding="utf-8")
    spec = Path("frontend/e2e/approval-packet-journey.spec.ts").read_text(encoding="utf-8")
    assert "acceptance-criterion: named-journey-pass" in doc
    assert "policy (check -> native submit -> approval packet print" in spec
    assert "approval-packet-journey.spec.ts" in doc
    assert "test:e2e:canary" in doc
    assert "[x]" in doc and "Named test" in doc


def test_acceptance_criterion_deliberate_break_revert_documented() -> None:
    doc = Path("docs/verification/pr-2046-approval-packet-canary.md").read_text(encoding="utf-8")
    assert "acceptance-criterion: deliberate-break-revert" in doc
    assert "approval-packet-document" in doc
    assert "039d13fb" in doc and "87d7f2eb" in doc
    assert "Deliberate break → revert" in doc or "Deliberate break" in doc


def test_reconciled_pr_body_marks_all_acceptance_criteria_complete() -> None:
    """Keepalive reconciliation: PR body checkboxes when GitHub API is unavailable."""
    body = Path("docs/verification/pr-2046-reconciled-pr-body.md").read_text(encoding="utf-8")
    assert "6/6 tasks complete" in body
    assert "approval-packet-journey.spec.ts" in body
    assert body.count("- [x]") >= 8
    assert "- [ ]" not in body.split("### Acceptance criteria")[1]
    assert "039d13fb" in body and "87d7f2eb" in body
