"""Verify the issue-specific handoff without writing the protected actual ledger."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from scripts import ledger_validate

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/issue-2025"
LEDGER = Path(".agents/issue-2007-ledger.yml")
FIXTURES = ROOT / "tests/fixtures/issue_2025_ledger"


def read_receipt(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


@pytest.fixture
def original_ledger() -> str:
    # Pin the input so these tests remain valid after an authorized writer
    # applies the proposal to the actual ledger.
    return (FIXTURES / "original.yml").read_text(encoding="utf-8")


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
    commit_files = json.loads((FIXTURES / "commit-files.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(ledger_validate, "_COMMIT_FILES_CACHE", commit_files)
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("LEDGER_VALIDATE_STRICT", "1")
    path = tmp_path / "reconciled-ledger.yml"
    path.write_text(yaml.safe_dump(proposed_ledger), encoding="utf-8")
    assert ledger_validate.validate_ledger(path) == []


@pytest.mark.parametrize(
    ("phase", "diagnostic", "tool_pins"),
    [
        ("failed", "ResolutionImpossible", ("0.17.2", "2.4.0", "9.1.1")),
        ("successful", "No broken requirements found.", ("0.17.3", "2.4.1", "9.2.0")),
    ],
)
def test_pin_reconciliation_matches_historical_editable_installs(
    proposed_ledger: dict, phase: str, diagnostic: str, tool_pins: tuple[str, str, str]
):
    """Bind each diagnosis to the selected editable checkout and its tool pins."""
    notes = task_notes(proposed_ledger, "task-05")
    tasks = {task["id"]: task for task in proposed_ledger["tasks"]}
    assert tasks["task-05"]["status"] == "deferred"
    provenance = read_receipt("fixture-provenance.json")
    log = (EVIDENCE / f"{phase}-install-excerpts.log").read_text(encoding="utf-8")
    fixture = next(
        item for item in provenance if item["fixture"] == f"{phase}/travel-plan-permission.toml"
    )
    checkout = fixture["source_url"].split("/blob/")[1].split("/")[0]
    # A SHA appearing elsewhere in the log is insufficient: it must be the
    # actual TPP checkout input, with no conflicting selection in that run.
    assert set(re.findall(r"\bTPP_PINNED_REF: ([0-9a-f]{40})\b", log)) == {checkout}
    pins = ", ".join(
        f"{tool}=={version}" for tool, version in zip(("ruff", "mypy", "pytest"), tool_pins)
    )
    assert f"checkout {checkout} has {pins}" in notes
    assert f"Collecting ruff=={tool_pins[0]} (from travel-plan-permission==0.1.0)" in log
    assert 'pip install -e ".[dev]" -e "../trip-planner[dev]"' in log
    assert diagnostic in log
    assert "PyPI-publication diagnosis" in notes and "superseded" in notes
    assert "No source pin edit was required or performed" in notes


@pytest.mark.parametrize("phase", ["failed", "successful"])
def test_install_logs_bind_resolved_checkouts_to_historical_metadata(phase: str):
    """Configured refs alone do not prove which source pip actually installed."""
    log = (EVIDENCE / f"{phase}-install-excerpts.log").read_text(encoding="utf-8")
    provenance = read_receipt("fixture-provenance.json")
    checkouts = {}
    for project in ("travel-plan-permission", "trip-planner"):
        source = next(item for item in provenance if item["fixture"] == f"{phase}/{project}.toml")
        checkout = source["source_url"].split("/blob/")[1].split("/")[0]
        checkouts[project] = checkout
        snapshot = (
            ROOT / "tests/fixtures/tpp_dev_pins" / checkout / "pyproject.toml"
            if project == "travel-plan-permission"
            else FIXTURES / f"{phase}-trip-planner.toml"
        )
        original = snapshot.read_bytes()
        blob = b"blob " + str(len(original)).encode("ascii") + b"\0" + original
        assert hashlib.sha1(blob).hexdigest() == source["git_blob"]
        metadata = tomllib.loads(original.decode("utf-8"))
        for raw in metadata["project"]["optional-dependencies"]["dev"]:
            requirement = Requirement(raw)
            if requirement.name in {"ruff", "mypy", "pytest"}:
                assert f"Collecting {requirement} (from {project}==0.1.0)" in log

    assert set(re.findall(r"\bTPP_RESOLVED_SHA=([0-9a-f]{40})\b", log)) == {
        checkouts["travel-plan-permission"]
    }
    assert set(re.findall(r"HEAD is now at \w+ Merge ([0-9a-f]{40}) into", log)) == {
        checkouts["trip-planner"]
    }
    if phase == "successful":
        assert checkouts["trip-planner"] == read_receipt("merged-pr.json")["headRefOid"]


@pytest.mark.parametrize(
    ("phase", "diagnostic"),
    [("failed", "ERROR: ResolutionImpossible:"), ("successful", "No broken requirements found.")],
)
def test_joint_install_resolves_both_local_sources_before_recorded_outcome(
    phase: str, diagnostic: str
):
    """Do not mistake a planner-only install or an unrelated pip check for the joint install."""
    log = (EVIDENCE / f"{phase}-install-excerpts.log").read_text(encoding="utf-8")
    events = []
    for line in log.splitlines():
        job, _, event = line.split("\t", 2)
        assert job == "cross-repo-full-product"
        timestamp, message = event.split(" ", 1)
        events.append((datetime.fromisoformat(timestamp), message.strip()))
    assert [timestamp for timestamp, _ in events] == sorted(timestamp for timestamp, _ in events)

    command = '.venv/bin/python -m pip install -e ".[dev]" -e "../trip-planner[dev]"'
    (install_start,) = [
        index for index, (_, message) in enumerate(events) if message == f"^[[36;1m{command}^[[0m"
    ]
    (outcome,) = [index for index, (_, message) in enumerate(events) if diagnostic in message]
    assert install_start < outcome
    install = events[install_start : outcome + 1]
    messages = [message for _, message in install]
    assert "^[[36;1m.venv/bin/python -m pip check^[[0m" in messages
    # These are pip's actual source reads after the joint command, not checkout
    # settings or the earlier successful planner-only installation.
    assert [message for message in messages if message.startswith("Obtaining file:")] == [
        "Obtaining file:///home/runner/work/trip-planner/trip-planner/Travel-Plan-Permission",
        "Obtaining file:///home/runner/work/trip-planner/trip-planner/trip-planner",
    ]
    assert sum("ResolutionImpossible" in message for _, message in events) == (phase == "failed")
    assert sum(message == "No broken requirements found." for _, message in events) == (
        phase == "successful"
    )
    if phase == "successful":
        smoke = read_receipt("smoke-run.json")
        job = next(job for job in smoke["jobs"] if job["name"] == "cross-repo-full-product")
        step = next(
            step
            for step in job["steps"]
            if step["name"] == "Install Travel-Plan-Permission dependencies"
        )
        started = datetime.fromisoformat(step["startedAt"])
        finished = datetime.fromisoformat(step["completedAt"])
        assert all(
            started <= timestamp.replace(microsecond=0) <= finished for timestamp, _ in install
        )


def test_checkout_fix_matches_preserved_tpp_metadata(proposed_ledger: dict):
    """Check the claimed resolution against the selected producer's real metadata."""
    notes = task_notes(proposed_ledger, "task-05")
    provenance = read_receipt("fixture-provenance.json")
    source = next(
        item for item in provenance if item["fixture"] == "successful/travel-plan-permission.toml"
    )
    checkout = source["source_url"].split("/blob/")[1].split("/")[0]
    snapshot = ROOT / "tests/fixtures/tpp_dev_pins" / checkout / "pyproject.toml"
    metadata = tomllib.loads(snapshot.read_text(encoding="utf-8"))
    requirements = {
        requirement.name: requirement
        for raw in metadata["project"]["optional-dependencies"]["dev"]
        if (requirement := Requirement(raw)).name in {"ruff", "mypy", "pytest"}
    }
    assert requirements.keys() == {"ruff", "mypy", "pytest"}
    pins = ", ".join(str(requirements[tool]) for tool in ("ruff", "mypy", "pytest"))
    # Failed and successful metadata share a note: match the successful clause
    # so a stale requirement cannot pass just by appearing in the failed clause.
    assert f"Successful checkout {checkout} has {pins}, matching planner dev pins." in notes

    failed = (EVIDENCE / "failed-install-excerpts.log").read_text(encoding="utf-8")
    successful = (EVIDENCE / "successful-install-excerpts.log").read_text(encoding="utf-8")
    ruff = str(requirements["ruff"])
    # The successful producer matches the planner pin already present in the
    # failed run. Merely changing the diagnosis to say "matching pins" is not
    # evidence that the pinned checkout actually supplies those requirements.
    assert f"trip-planner[dev] 0.1.0 depends on {ruff};" in failed
    assert f"Collecting {ruff} (from travel-plan-permission==0.1.0)" in successful
    assert "ResolutionImpossible" not in successful
    assert "Trip-planner commit 29c6aa01 changes TPP_PINNED_REF" in notes
    assert "adds a dev-pin check before the joint install" in notes


def test_failed_checkout_diagnosis_matches_original_metadata(proposed_ledger: dict):
    """Keep all three original conflicts grounded in the failed editable source."""
    provenance = read_receipt("fixture-provenance.json")
    source = next(
        item for item in provenance if item["fixture"] == "failed/travel-plan-permission.toml"
    )
    checkout = source["source_url"].split("/blob/")[1].split("/")[0]
    snapshot = ROOT / "tests/fixtures/tpp_dev_pins" / checkout / "pyproject.toml"
    original = snapshot.read_bytes()
    # This is the complete original blob, rather than an edited metadata excerpt.
    blob = b"blob " + str(len(original)).encode("ascii") + b"\0" + original
    assert hashlib.sha1(blob).hexdigest() == source["git_blob"]
    metadata = tomllib.loads(original.decode("utf-8"))
    requirements = {
        requirement.name: requirement
        for raw in metadata["project"]["optional-dependencies"]["dev"]
        if (requirement := Requirement(raw)).name in {"ruff", "mypy", "pytest"}
    }
    assert requirements.keys() == {"ruff", "mypy", "pytest"}
    pins = ", ".join(str(requirements[tool]) for tool in ("ruff", "mypy", "pytest"))
    assert f"Failed TPP checkout {checkout} has {pins}." in task_notes(proposed_ledger, "task-05")
    failed_log = (EVIDENCE / "failed-install-excerpts.log").read_text(encoding="utf-8")
    assert f"Collecting {requirements['ruff']} (from travel-plan-permission==0.1.0)" in failed_log
    assert f"TPP_PINNED_REF: {checkout}" in failed_log
    assert "ResolutionImpossible" in failed_log


@pytest.mark.parametrize("tool", ["ruff", "mypy", "pytest"])
def test_planner_pins_already_match_successful_producer(proposed_ledger: dict, tool: str):
    """The passing smoke changed the producer checkout, not the planner's tool pins."""
    provenance = read_receipt("fixture-provenance.json")
    planner_pins = {}
    heads = {}
    for phase in ("failed", "successful"):
        source = next(
            item for item in provenance if item["fixture"] == f"{phase}/trip-planner.toml"
        )
        heads[phase] = source["source_url"].split("/blob/")[1].split("/")[0]
        original = (FIXTURES / f"{phase}-trip-planner.toml").read_bytes()
        blob = b"blob " + str(len(original)).encode("ascii") + b"\0" + original
        assert hashlib.sha1(blob).hexdigest() == source["git_blob"]
        metadata = tomllib.loads(original.decode("utf-8"))
        planner_pins[phase] = next(
            str(requirement)
            for raw in metadata["project"]["optional-dependencies"]["dev"]
            if (requirement := Requirement(raw)).name == tool
        )

    producer_source = next(
        item for item in provenance if item["fixture"] == "successful/travel-plan-permission.toml"
    )
    producer_head = producer_source["source_url"].split("/blob/")[1].split("/")[0]
    producer = tomllib.loads(
        (ROOT / "tests/fixtures/tpp_dev_pins" / producer_head / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    producer_pin = next(
        str(requirement)
        for raw in producer["project"]["optional-dependencies"]["dev"]
        if (requirement := Requirement(raw)).name == tool
    )
    assert planner_pins["failed"] == planner_pins["successful"] == producer_pin
    assert heads["successful"] == read_receipt("smoke-run.json")["headSha"]

    # A note saying the planner used old pins would misidentify the actual
    # successful mechanism even though the existing producer checks still pass.
    notes = task_notes(proposed_ledger, "task-03")
    version = str(Requirement(producer_pin).specifier).removeprefix("==")
    assert f"{tool} {version}" in notes.casefold()
    assert f"failed head {heads['failed'][:8]}" in notes
    assert f"final head {heads['successful'][:8]}" in notes
    assert "already resolved the trip-planner editable dev extra" in notes
    assert "lockfile change on top of smoke fix 29c6aa01" in notes
    assert "Published package conflict" not in notes


def test_smoke_and_local_command_records_match_receipts(proposed_ledger: dict):
    """Require successful resolver and install steps at the head that merged."""
    notes = task_notes(proposed_ledger, "task-14")
    smoke = read_receipt("smoke-run.json")
    merged = read_receipt("merged-pr.json")
    acceptance = read_receipt("acceptance.json")
    assert smoke["headSha"] == merged["headRefOid"]
    assert smoke["conclusion"] == "success"
    assert merged["state"] == "MERGED"
    job = next(job for job in smoke["jobs"] if job["name"] == "cross-repo-full-product")
    assert job["status"] == "completed" and job["conclusion"] == "success"
    steps = {step["name"]: step for step in job["steps"]}
    required_steps = (
        "Check dev pins co-resolve with pinned TPP",
        "Install Travel-Plan-Permission dependencies",
        "Run full-product-check against sibling TPP checkout",
    )
    for name in required_steps:
        assert steps[name]["status"] == "completed"
        assert steps[name]["conclusion"] == "success"
    assert [steps[name]["number"] for name in required_steps] == sorted(
        steps[name]["number"] for name in required_steps
    )
    assert datetime.fromisoformat(job["completedAt"]) < datetime.fromisoformat(merged["mergedAt"])
    assert smoke["headSha"] in notes
    assert merged["mergeCommit"]["oid"] in notes
    assert acceptance["documented_local_command"] in notes
    assert acceptance["documented_local_command_commit"] in notes
    assert acceptance["documented_local_command_exit_code"] == 0
    assert "Exit 0" in notes


def test_successful_smoke_executed_live_pin_guard_before_joint_install():
    """A green step alone does not prove the live checkout checks actually ran."""
    log = (EVIDENCE / "successful-install-excerpts.log").read_text(encoding="utf-8")
    events = [line.split("\t", 2)[2].split(" ", 1) for line in log.splitlines()]
    command = "##[group]Run python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q"
    guard_start = next(index for index, (_, message) in enumerate(events) if message == command)
    install_start = next(
        index
        for index, (_, message) in enumerate(events)
        if 'pip install -e ".[dev]" -e "../trip-planner[dev]"' in message
    )
    guard_events = events[guard_start:install_start]
    messages = [message.strip() for _, message in guard_events]
    resolved = next(
        message.removeprefix("TPP_RESOLVED_SHA=")
        for _, message in events
        if message.startswith("TPP_RESOLVED_SHA=")
    )
    assert f"TPP_PINNED_REF: {resolved}" in messages
    assert "TPP_REPO_PATH: ../Travel-Plan-Permission" in messages
    # Match the entire pytest summary: a partial pass with skipped live checks
    # must not count as evidence that both editable checkouts were inspected.
    (result_time,) = (
        timestamp
        for timestamp, message in guard_events
        if re.fullmatch(r"[1-9]\d* passed(?:, \d+ warnings)? in \d+(?:\.\d+)?s", message)
    )
    smoke = read_receipt("smoke-run.json")
    job = next(job for job in smoke["jobs"] if job["name"] == "cross-repo-full-product")
    guard = next(
        step for step in job["steps"] if step["name"] == "Check dev pins co-resolve with pinned TPP"
    )
    # The API records whole seconds while job-log timestamps include fractions.
    started = datetime.fromisoformat(events[guard_start][0]).replace(microsecond=0)
    finished = datetime.fromisoformat(result_time).replace(microsecond=0)
    assert datetime.fromisoformat(guard["startedAt"]) <= started <= finished
    assert finished <= datetime.fromisoformat(guard["completedAt"])
    assert datetime.fromisoformat(result_time) < datetime.fromisoformat(events[install_start][0])


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


def test_supported_runtime_receipt_binds_source_interpreter_and_mutation():
    """A passing fallback run alone cannot establish supported-runtime evidence."""
    receipt = read_receipt("supported-runtime.json")
    acceptance = read_receipt("acceptance.json")
    assert receipt["source_repository"] == acceptance["owning_repository"]
    assert receipt["source_commit"] == acceptance["owning_commit"]
    # Focused snapshot verification does not establish full-checkout CI.
    assert receipt["validation_kind"] == "local-source-snapshot"
    assert receipt["ci_verified"] is False
    runtime = receipt["runtime"]
    assert Version(runtime["version"]) in SpecifierSet(receipt["requires_python"])
    assert receipt["requires_python"] == ">=3.13"
    assert receipt["command"] == [
        runtime["executable"],
        "-m",
        "pytest",
        "tests/test_dependency_resolution.py",
        "-m",
        "not slow",
    ]
    sources = {item["path"]: item for item in receipt["source_files"]}
    for path in (
        "pyproject.toml",
        "tests/conftest.py",
        "tests/test_dependency_resolution.py",
        "scripts/sync_dev_dependencies.py",
        ".github/workflows/autofix-versions.env",
        "tests/fixtures/dependency_resolution/editable_backend.py",
    ):
        assert path in sources
    for source in sources.values():
        assert re.fullmatch(r"[0-9a-f]{40}", source["source_blob"])
        assert source["verified_blob"] == source["source_blob"]
    phases = receipt["phases"]
    assert [(phase["phase"], phase["exit_code"]) for phase in phases] == [
        ("baseline", 0),
        ("mutation", 1),
        ("restored", 0),
    ]
    fixture = "tests/fixtures/dependency_resolution/successful/travel-plan-permission.toml"
    assert phases[0]["fixture_blob"] == phases[2]["fixture_blob"] == sources[fixture]["source_blob"]
    assert phases[1]["fixture_blob"] != sources[fixture]["source_blob"]
    assert receipt["source_restored"] is True
    for phase in phases:
        assert 0 < phase["wall_seconds"] < 120
        log = (EVIDENCE / phase["log"]).read_text(encoding="utf-8")
        assert f"Python {runtime['version']}" in log
        assert f"pytest-{runtime['packages']['pytest']}" in log
        assert f"rootdir: {receipt['cwd']}" in log
        assert "configfile: pyproject.toml" in log and "collected 8 items" in log
        assert "ResolutionImpossible" in log if phase["exit_code"] else "8 passed" in log


def test_sync_classification_matches_merged_head(proposed_ledger: dict):
    notes = task_notes(proposed_ledger, "task-16")
    report = read_receipt("sync-core-report.json")
    merged = read_receipt("merged-pr.json")
    assert datetime.fromisoformat(report["timestamp"]) > datetime.fromisoformat(merged["mergedAt"])
    assert report["item"]["target"] == "stranske/trip-planner#2006"
    assert report["item"]["disposition"] == "delivered"
    assert report["item"]["error"] is None and report["item"]["handoffs"] == []
    assert report["target_state"]["head"] == merged["headRefOid"]
    for value in (report["round"], report["timestamp"], report["target_state"]["head"]):
        assert value in notes
    assert "No dependency-pin finding" in notes
