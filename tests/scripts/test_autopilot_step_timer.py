import json
from pathlib import Path

import pytest
from scripts import autopilot_step_timer as timer


@pytest.mark.parametrize(
    ("event", "fmt", "expected"),
    [
        ("start", "epoch-ms", "AUTOPILOT_STEP_STARTED_AT_MS"),
        ("end", "epoch-ms", "AUTOPILOT_STEP_ENDED_AT_MS"),
        ("start", "iso", "AUTOPILOT_STEP_STARTED_AT"),
        ("end", "iso", "AUTOPILOT_STEP_ENDED_AT"),
    ],
)
def test_default_key(event: str, fmt: str, expected: str) -> None:
    assert timer.default_key(event, fmt) == expected


def test_timestamp_value_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timer, "_utc_now_epoch_ms", lambda: 1234)

    assert timer.timestamp_value("epoch-ms") == "1234"


def test_timestamp_value_iso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timer, "_utc_now_iso", lambda: "2025-01-02T03:04:05Z")

    assert timer.timestamp_value("iso") == "2025-01-02T03:04:05Z"


def test_append_env_writes_value(tmp_path: Path) -> None:
    path = tmp_path / "env.out"

    timer.append_env(path, "AUTOPILOT_STEP_STARTED_AT_MS", "999")

    assert path.read_text(encoding="utf-8") == "AUTOPILOT_STEP_STARTED_AT_MS=999\n"


def test_env_path_reads_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_path = tmp_path / "env.out"
    monkeypatch.setenv("GITHUB_ENV", str(env_path))

    assert timer.env_path("GITHUB_ENV") == env_path


def test_env_path_errors_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    with pytest.raises(ValueError, match="GITHUB_OUTPUT is not set"):
        timer.env_path("GITHUB_OUTPUT")


def test_main_writes_to_env_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "step.env"
    monkeypatch.setattr(timer, "_utc_now_epoch_ms", lambda: 5678)

    exit_code = timer.main(["--event", "start", "--env-path", str(env_path)])

    assert exit_code == 0
    assert env_path.read_text(encoding="utf-8") == "AUTOPILOT_STEP_STARTED_AT_MS=5678\n"
    assert capsys.readouterr().out == ""


def test_main_writes_to_output_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output_path = tmp_path / "step.out"
    monkeypatch.setattr(timer, "_utc_now_iso", lambda: "2025-01-02T03:04:05Z")

    exit_code = timer.main(["--event", "end", "--format", "iso", "--output-path", str(output_path)])

    assert exit_code == 0
    assert (
        output_path.read_text(encoding="utf-8") == "AUTOPILOT_STEP_ENDED_AT=2025-01-02T03:04:05Z\n"
    )
    assert capsys.readouterr().out == ""


def test_main_writes_failure_summary_when_github_env_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary_path = tmp_path / "summary.ndjson"
    monkeypatch.setenv("AUTOPILOT_METRICS_SUMMARY_PATH", str(summary_path))
    monkeypatch.setenv("AUTOPILOT_STEP_NAME", "format")
    monkeypatch.setenv("GITHUB_RUN_ID", "run-123")
    monkeypatch.delenv("GITHUB_ENV", raising=False)

    exit_code = timer.main(["--event", "start", "--github-env"])

    assert exit_code == 1
    summary_lines = summary_path.read_text(encoding="utf-8").splitlines()
    assert len(summary_lines) == 1
    summary = json.loads(summary_lines[0])
    assert summary["summary_type"] == "autopilot-metrics-error"
    assert summary["component"] == "autopilot_step_timer"
    assert summary["step_name"] == "format"
    assert summary["error_category"] == "timer_error"
    assert summary["exit_code"] == 1
    assert summary["environment"]["github_run_id"] == "run-123"


def test_main_writes_failure_summary_when_github_output_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary_path = tmp_path / "summary.ndjson"
    monkeypatch.setenv("AUTOPILOT_METRICS_SUMMARY_PATH", str(summary_path))
    monkeypatch.setenv("AUTOPILOT_STEP_NAME", "collect")
    monkeypatch.setenv("GITHUB_RUN_ID", "run-456")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    exit_code = timer.main(["--event", "end", "--github-output"])

    assert exit_code == 1
    summary_lines = summary_path.read_text(encoding="utf-8").splitlines()
    assert len(summary_lines) == 1
    summary = json.loads(summary_lines[0])
    assert summary["summary_type"] == "autopilot-metrics-error"
    assert summary["component"] == "autopilot_step_timer"
    assert summary["step_name"] == "collect"
    assert summary["error_category"] == "timer_error"
    assert summary["exit_code"] == 1
    assert summary["environment"]["github_run_id"] == "run-456"
