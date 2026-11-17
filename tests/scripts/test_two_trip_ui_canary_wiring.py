"""Structural guards for the approval-packet browser canary (issue / PR #2046).

The full journey is exercised by Playwright via ``scripts/run_two_trip_ui_canary.sh``.
These tests keep the TPP stub, npm script, and ApprovalPacket mount wired so a deliberate
removal of the packet DOM (negative probe) fails CI before the expensive canary run.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_canary_script_starts_tpp_stub_and_exports_tpp_base_url() -> None:
    script = Path("scripts/run_two_trip_ui_canary.sh").read_text(encoding="utf-8")
    assert "scripts/tpp_http_canary_stub.py" in script
    assert 'TPP_BASE_URL="${tpp_url}"' in script
    assert "npm --prefix frontend run test:e2e:canary" in script
    assert "simulated TPP transport" in script


def test_frontend_canary_runner_includes_approval_packet_journey() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    canary_script = package["scripts"]["test:e2e:canary"]
    assert "e2e/approval-packet-journey.spec.ts" in canary_script
    assert "e2e/two-trip-canary.spec.ts" in canary_script


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


def test_deliberate_break_negative_probe_recorded_in_branch_history() -> None:
    """Acceptance: deliberate mount removal and revert are evidenced on this PR branch."""
    log = subprocess.run(
        ["git", "log", "--oneline", "-30"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.lower()
    assert "negative probe" in log and "approvalpacket" in log
    assert "restore approvalpacket" in log or "restore approval packet" in log
