from pathlib import Path

import pytest

from scripts import check_full_product_verification as verifier


def _make_repo_with_venv(tmp_path: Path) -> tuple[Path, Path]:
    repo_path = tmp_path / "Travel-Plan-Permission"
    venv_python = repo_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    return repo_path, venv_python


def test_started_tpp_service_starts_and_terminates_cleanly(monkeypatch, tmp_path: Path) -> None:
    repo_path, _ = _make_repo_with_venv(tmp_path)

    class FakeProcess:
        def __init__(self, command, **kwargs):
            self.command = command
            self.kwargs = kwargs
            self._poll = None
            self.terminated = False
            self.wait_calls = 0

        def poll(self):
            return self._poll

        def terminate(self):
            self.terminated = True
            self._poll = 0

        def wait(self, timeout):
            self.wait_calls += 1
            return 0

    process_holder: dict[str, FakeProcess] = {}

    def fake_popen(command, **kwargs):
        proc = FakeProcess(command, **kwargs)
        process_holder["proc"] = proc
        return proc

    monkeypatch.setattr(verifier.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(verifier, "_wait_for_http", lambda _url: None)
    monkeypatch.setattr(verifier, "_free_local_port", lambda _preferred: 42123)

    with verifier._started_tpp_service(
        {
            "TPP_REPO_PATH": str(repo_path),
            "TPP_ACCESS_TOKEN": "token",
            "TPP_OIDC_PROVIDER": "google",
        }
    ) as (base_url, process):
        assert base_url.startswith("http://127.0.0.1:")
        assert process is process_holder["proc"]

    process = process_holder["proc"]
    assert process.command[0] == str(repo_path / ".venv" / "bin" / "python")
    assert process.command[1:3] == ["-m", "travel_plan_permission.http_service"]
    assert process.terminated is True
    assert process.wait_calls == 1


def test_started_tpp_service_readiness_failure_includes_captured_stderr(
    monkeypatch, tmp_path: Path
) -> None:
    repo_path, venv_python = _make_repo_with_venv(tmp_path)

    class FakeProcess:
        def __init__(self, command, **kwargs):
            self.command = command
            kwargs["stderr"].write(b"ModuleNotFoundError: No module named 'jinja2'\n")
            kwargs["stderr"].flush()

        def poll(self):
            return 1

        def terminate(self):  # pragma: no cover - process has already exited
            raise AssertionError("process already exited")

    monkeypatch.setattr(verifier.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(
        verifier,
        "_wait_for_http",
        lambda _url: (_ for _ in ()).throw(verifier.VerificationFailure("not ready")),
    )
    monkeypatch.setattr(verifier, "_free_local_port", lambda _preferred: 43123)

    with pytest.raises(verifier.VerificationFailure) as exc_info:
        with verifier._started_tpp_service(
            {
                "TPP_REPO_PATH": str(repo_path),
                "TPP_ACCESS_TOKEN": "token",
                "TPP_OIDC_PROVIDER": "google",
            }
        ):
            pass

    message = str(exc_info.value)
    assert str(venv_python) in message
    assert '"interpreter"' in message
    assert "ModuleNotFoundError: No module named 'jinja2'" in message
    assert "stderr_tail" in message
