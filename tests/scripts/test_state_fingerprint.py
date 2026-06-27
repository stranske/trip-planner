import json

import pytest
from scripts import state_fingerprint


class FakeStorage:
    def __init__(self, prior: str | None = None) -> None:
        self._prior = prior
        self.writes: list[str] = []

    def read_fingerprint(self, workflow_name: str) -> str | None:
        return self._prior

    def write_fingerprint(self, workflow_name: str, fingerprint_hash: str) -> None:
        self.writes.append(fingerprint_hash)
        self._prior = fingerprint_hash


class MarkerStorage:
    def __init__(self, value: str | None = None) -> None:
        self.value = value
        self.writes: list[str] = []

    def read_fingerprint(self, workflow_name: str) -> str | None:
        return state_fingerprint._extract_hash(self.value, workflow_name)

    def write_fingerprint(self, workflow_name: str, fingerprint_hash: str) -> None:
        self.value = state_fingerprint._build_marker(workflow_name, fingerprint_hash)
        self.writes.append(fingerprint_hash)


def test_compute_fingerprint_is_stable_for_equivalent_inputs() -> None:
    first = state_fingerprint.compute_fingerprint("wf", {"b": 2, "a": {"d": 4, "c": 3}})
    second = state_fingerprint.compute_fingerprint("wf", {"a": {"c": 3, "d": 4}, "b": 2})

    assert first == second


def test_compute_fingerprint_changes_when_inputs_change() -> None:
    unchanged = state_fingerprint.compute_fingerprint("wf", {"head_sha": "abc"})
    changed = state_fingerprint.compute_fingerprint("wf", {"head_sha": "def"})

    assert unchanged != changed


def test_compute_fingerprint_changes_when_workflow_name_changes() -> None:
    first = state_fingerprint.compute_fingerprint("wf-a", {"head_sha": "abc"})
    second = state_fingerprint.compute_fingerprint("wf-b", {"head_sha": "abc"})

    assert first != second


def test_compare_fingerprint_first_run_when_no_prior() -> None:
    storage = FakeStorage()

    decision = state_fingerprint.compare_fingerprint("wf", {"head_sha": "abc"}, storage)

    assert decision.should_run is True
    assert decision.reason == "no-prior-fingerprint"
    assert decision.prior_hash is None
    assert decision.current_hash == state_fingerprint.compute_fingerprint("wf", {"head_sha": "abc"})


def test_compare_fingerprint_skips_when_state_is_unchanged() -> None:
    current = {"head_sha": "abc", "labels": ["autofix"]}
    prior = state_fingerprint.compute_fingerprint("wf", current)
    storage = FakeStorage(prior)

    decision = state_fingerprint.compare_fingerprint("wf", current, storage)

    assert decision.should_run is False
    assert decision.reason == "fingerprint-match"
    assert decision.prior_hash == decision.current_hash


def test_compare_fingerprint_runs_when_state_changes() -> None:
    prior = state_fingerprint.compute_fingerprint("wf", {"head_sha": "old"})
    storage = FakeStorage(prior)

    decision = state_fingerprint.compare_fingerprint("wf", {"head_sha": "new"}, storage)

    assert decision.should_run is True
    assert decision.reason == "fingerprint-changed"
    assert decision.prior_hash == prior
    assert decision.current_hash != prior


def test_extract_hash_reads_html_marker_payload() -> None:
    fingerprint_hash = "a" * 64
    marker = state_fingerprint._build_marker("wf", fingerprint_hash)

    assert state_fingerprint._extract_hash(marker, "wf") == fingerprint_hash


def test_extract_hash_accepts_raw_json_storage_value() -> None:
    fingerprint_hash = "b" * 64

    assert (
        state_fingerprint._extract_hash(json.dumps({"hash": fingerprint_hash}), "wf")
        == fingerprint_hash
    )


def test_extract_hash_tolerates_malformed_json() -> None:
    storage = MarkerStorage(
        f'<!-- {state_fingerprint.MARKER_PREFIX}:wf:{state_fingerprint.MARKER_VERSION} {{"hash": -->'
    )

    decision = state_fingerprint.compare_fingerprint("wf", {"head_sha": "abc"}, storage)

    assert decision.should_run is True
    assert decision.reason == "no-prior-fingerprint"
    assert decision.prior_hash is None


@pytest.mark.parametrize(
    "payload",
    [
        '{"hash":"not-hex"}',
        '{"hash":"abc"}',
        '{"hash":"' + "g" * 64 + '"}',
        '{"hash":123}',
    ],
)
def test_extract_hash_rejects_invalid_hashes(payload: str) -> None:
    assert state_fingerprint._extract_hash(payload, "wf") is None


def test_variable_name_sanitizes_and_truncates_long_workflow_names() -> None:
    workflow_name = "Verifier " + ("very-long-name-" * 20)

    first = state_fingerprint._variable_name(workflow_name)
    second = state_fingerprint._variable_name(workflow_name)

    assert first == second
    assert first.startswith("STATE_FINGERPRINT_VERIFIER_")
    assert len(first) <= 100


def test_variable_name_sanitizes_special_characters() -> None:
    name = state_fingerprint._variable_name("agents/81-gate followups")

    assert name.startswith("STATE_FINGERPRINT_AGENTS_81_GATE_FOLLOWUPS_")
    assert len(name) <= 100
    assert "/" not in name
    assert " " not in name


def test_compare_cli_rejects_invalid_inputs_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = state_fingerprint.main(
        ["compare", "--workflow", "wf", "--inputs", "{not json", "--storage", "pr-comment"]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "invalid --inputs JSON" in captured.err


def test_store_cli_rejects_invalid_hash(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = state_fingerprint.main(
        ["store", "--workflow", "wf", "--hash", "not-a-valid-hash", "--storage", "pr-comment"]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--hash must be a 64-character hex SHA-256 fingerprint" in captured.err
