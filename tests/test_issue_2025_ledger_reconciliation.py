"""Verify the issue-specific handoff without writing the protected actual ledger."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.ledger_validate import validate_ledger

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/issue-2025"
LEDGER = Path(".agents/issue-2007-ledger.yml")
LEDGER_BASE = "6f2bbe03c8b1c36c3feadf4cc56b0965c927cf5f"


def read_receipt(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


@pytest.fixture
def original_ledger() -> str:
    # Pin the input so these tests remain valid after an authorized writer
    # applies the proposal to the actual ledger.
    result = subprocess.run(
        ["git", "show", f"{LEDGER_BASE}:{LEDGER.as_posix()}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return result.stdout


@pytest.fixture
def proposed_ledger(tmp_path: Path, original_ledger: str) -> dict:
    """Apply only to a temporary copy; never modify or replace ROOT / LEDGER."""
    copied = tmp_path / LEDGER
    copied.parent.mkdir()
    copied.write_text(original_ledger, encoding="utf-8")
    result = subprocess.run(
        ["git", "apply", "--", str(EVIDENCE / "ledger-reconciliation.patch")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()} == {
        LEDGER
    }
    return yaml.safe_load(copied.read_text(encoding="utf-8"))


def task_notes(ledger: dict, task_id: str) -> str:
    return "\n".join(next(task for task in ledger["tasks"] if task["id"] == task_id)["notes"])


def test_reconciled_tasks_pass_existing_ledger_validator(
    proposed_ledger: dict, original_ledger: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # The original ledger has malformed YAML notes. Preserve its task inventory
    # and unrelated statuses while validating the complete proposed document.
    before = dict(
        re.findall(
            r"^  - id: (\S+).*?^    status: (\w+)", original_ledger, re.MULTILINE | re.DOTALL
        )
    )
    after = {task["id"]: task for task in proposed_ledger["tasks"]}
    assert before.keys() == after.keys()
    assert {key for key in before if before[key] != after[key]["status"]} == {
        "task-05",
        "task-14",
        "task-15",
        "task-16",
    }
    # This calls the production schema and commit validator, including real
    # local Git lookups. No missing-commit or shallow-history exemption is used.
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("LEDGER_VALIDATE_STRICT", "1")
    path = tmp_path / "reconciled-ledger.yml"
    path.write_text(yaml.safe_dump(proposed_ledger), encoding="utf-8")
    assert validate_ledger(path) == []


def test_pin_reconciliation_matches_historical_editable_installs(proposed_ledger: dict):
    notes = task_notes(proposed_ledger, "task-05")
    tasks = {task["id"]: task for task in proposed_ledger["tasks"]}
    assert tasks["task-05"]["status"] == "deferred"
    provenance = read_receipt("fixture-provenance.json")
    for phase, diagnostic in (
        ("failed", "ResolutionImpossible"),
        ("successful", "No broken requirements found."),
    ):
        log = (EVIDENCE / f"{phase}-install-excerpts.log").read_text(encoding="utf-8")
        fixture = next(
            item for item in provenance if item["fixture"] == f"{phase}/travel-plan-permission.toml"
        )
        checkout = fixture["source_url"].split("/blob/")[1].split("/")[0]
        assert checkout in log and checkout in notes
        assert 'pip install -e ".[dev]" -e "../trip-planner[dev]"' in log
        assert diagnostic in log
    assert "PyPI-publication diagnosis" in notes and "superseded" in notes
    assert "No source pin edit was required or performed" in notes


def test_smoke_and_local_command_records_match_receipts(proposed_ledger: dict):
    notes = task_notes(proposed_ledger, "task-14")
    smoke = read_receipt("smoke-run.json")
    merged = read_receipt("merged-pr.json")
    acceptance = read_receipt("acceptance.json")
    assert smoke["headSha"] == merged["headRefOid"]
    assert smoke["conclusion"] == "success"
    assert any(
        job["name"] == "cross-repo-full-product" and job["conclusion"] == "success"
        for job in smoke["jobs"]
    )
    assert smoke["headSha"] in notes
    assert merged["mergeCommit"]["oid"] in notes
    assert acceptance["documented_local_command"] in notes
    assert acceptance["documented_local_command_commit"] in notes
    assert acceptance["documented_local_command_exit_code"] == 0
    assert "Exit 0" in notes


def test_mutation_record_preserves_owning_commit_and_results(proposed_ledger: dict):
    notes = task_notes(proposed_ledger, "task-15")
    receipts = read_receipt("receipts.json")
    assert [(item["phase"], item["exit_code"]) for item in receipts] == [
        ("baseline", 0),
        ("mutation", 1),
        ("restored", 0),
    ]
    for receipt in receipts:
        assert receipt["commit"] in notes
        assert receipt["wall_seconds"] < 120
    assert "ResolutionImpossible" in (EVIDENCE / "mutation.log").read_text(encoding="utf-8")
    assert "Restored original bytes" in notes


def test_sync_classification_matches_merged_head(proposed_ledger: dict):
    notes = task_notes(proposed_ledger, "task-16")
    report = read_receipt("sync-core-report.json")
    merged = read_receipt("merged-pr.json")
    assert report["timestamp"] > merged["mergedAt"]
    assert report["item"]["target"] == "stranske/trip-planner#2006"
    assert report["item"]["disposition"] == "delivered"
    assert report["item"]["error"] is None and report["item"]["handoffs"] == []
    assert report["target_state"]["head"] == merged["headRefOid"]
    for value in (report["round"], report["timestamp"], report["target_state"]["head"]):
        assert value in notes
    assert "No dependency-pin finding" in notes
