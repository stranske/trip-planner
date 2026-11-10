"""Keep historical smoke evidence from closing unverified ledger work."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.reconcile_issue_2007 import BLOCK, reconciliation

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / ".agents/issue-2007-ledger.yml"
EVIDENCE = ROOT / "docs/evidence/issue-2025/run-reconciliation.json"


def test_reconciles_actual_receipts_without_claiming_unperformed_work() -> None:
    original = LEDGER.read_text(encoding="utf-8")
    updated = reconciliation(original, json.loads(EVIDENCE.read_text(encoding="utf-8")))
    before = BLOCK.findall(original)
    after = BLOCK.findall(updated)
    assert len(before) == len(after) == 21
    for old, new in zip(before, after, strict=True):
        task_id = old.splitlines()[0].removeprefix("  - id: ")
        if task_id not in ("task-05", "task-14"):
            assert old == new
            continue
        # Target notes become valid YAML; unrelated invalid historical notes
        # remain untouched so the patch stays within the two requested tasks.
        new = yaml.safe_load(new)[0]
        old_fields = yaml.safe_load(old.split("    notes:\n")[0])[0]
        assert new["status"] == ("deferred" if task_id == "task-05" else "blocked")
        assert new["finished_at"] is None
        assert new["commit"] == old_fields["commit"]
        assert new["title"] == old_fields["title"]
        assert any("final head fcb6e97" in note for note in new["notes"])
    assert reconciliation(updated, json.loads(EVIDENCE.read_text(encoding="utf-8"))) == updated


@pytest.mark.parametrize(
    ("section", "field", "value", "diagnostic"),
    [
        ("pull_request", "merged", False, "merged PR"),
        ("pull_request", "number", 2026, "merged PR"),
        ("pull_request", "head_sha", "a" * 40, "final head"),
        ("run_lookup", "commit_sha", "a" * 40, "final head"),
    ],
)
def test_rejects_unmerged_or_wrong_head_receipts(
    section: str, field: str, value: object, diagnostic: str
) -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    evidence[section][field] = value
    with pytest.raises(ValueError, match=diagnostic):
        reconciliation(LEDGER.read_text(encoding="utf-8"), evidence)


@pytest.mark.parametrize("target", ["run", "job", "job-run", "duplicate-job", "duplicate-run"])
def test_rejects_failed_or_ambiguous_smoke_receipts(target: str) -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    runs = evidence["run_lookup"]["workflow_runs"]
    if target == "run":
        runs[0]["conclusion"] = "failure"
    elif target == "job":
        evidence["jobs"][0]["conclusion"] = "failure"
    elif target == "job-run":
        evidence["jobs"][0]["run_id"] = 42449207754
    elif target == "duplicate-job":
        evidence["jobs"].append(copy.deepcopy(evidence["jobs"][0]))
    else:
        runs.append(copy.deepcopy(runs[0]))
    with pytest.raises(ValueError, match="run 42484305260"):
        reconciliation(LEDGER.read_text(encoding="utf-8"), evidence)


@pytest.mark.parametrize(
    ("run", "text", "diagnostic"),
    [
        ("42449207754", "pip install -e", "install inputs"),
        ("42484305260", "pip install -e", "install inputs"),
        ("42449207754", "ResolutionImpossible", "conflicting Ruff"),
        ("42484305260", "Merge fcb6e97", "final PR head"),
        ("42484305260", "Successfully installed", "resolved installation"),
        ("42449207754", "TPP_PINNED_REF", "pinned TPP checkouts"),
        ("42484305260", "TPP_PINNED_REF", "pinned TPP checkouts"),
    ],
)
def test_requires_install_and_checkout_evidence(run: str, text: str, diagnostic: str) -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    evidence["log_excerpts"][run] = [
        line for line in evidence["log_excerpts"][run] if text not in line
    ]
    with pytest.raises(ValueError, match=diagnostic):
        reconciliation(LEDGER.read_text(encoding="utf-8"), evidence)


def test_cli_emits_applicable_patch_and_leaves_input_unchanged(tmp_path: Path) -> None:
    ledger = tmp_path / ".agents/issue-2007-ledger.yml"
    ledger.parent.mkdir()
    original = LEDGER.read_bytes()
    ledger.write_bytes(original)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/reconcile_issue_2007.py"),
            "--evidence",
            str(EVIDENCE),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert ledger.read_bytes() == original
    assert "--- a/.agents/issue-2007-ledger.yml" in result.stdout
    # Check the patch with Git's parser in an isolated, writable repository.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    applied = subprocess.run(
        ["git", "apply", "-"],
        input=result.stdout,
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert applied.returncode == 0, applied.stderr
    assert ledger.read_text(encoding="utf-8") == reconciliation(
        original.decode(), json.loads(EVIDENCE.read_text(encoding="utf-8"))
    )


def test_cli_invalid_evidence_fails_without_patch(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/reconcile_issue_2007.py"),
            "--ledger",
            str(LEDGER),
            "--evidence",
            str(invalid),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    assert not result.stdout
    assert "Cannot reconcile ledger" in result.stderr
