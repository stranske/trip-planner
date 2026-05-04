from pathlib import Path
import stat
import time

import pytest

from scripts import check_full_product_verification as verifier


def _make_repo_with_venv(tmp_path: Path) -> tuple[Path, Path]:
    repo_path = tmp_path / "Travel-Plan-Permission"
    venv_python = repo_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    return repo_path, venv_python


def _make_runnable_tpp_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_path, venv_python = _make_repo_with_venv(tmp_path)
    package_path = repo_path / "src" / "travel_plan_permission"
    package_path.mkdir(parents=True)
    (package_path / "__init__.py").write_text("", encoding="utf-8")
    (package_path / "http_service.py").write_text(
        """
import argparse
import time


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.parse_args()
    while True:
        time.sleep(0.1)


if __name__ == "__main__":
    main()
""".strip() + "\n",
        encoding="utf-8",
    )
    venv_python.write_text(
        f'#!/usr/bin/env bash\nexec {verifier.sys.executable} "$@"\n',
        encoding="utf-8",
    )
    venv_python.chmod(venv_python.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return repo_path, venv_python


def _make_missing_deps_tpp_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_path, venv_python = _make_repo_with_venv(tmp_path)
    package_path = repo_path / "src" / "travel_plan_permission"
    package_path.mkdir(parents=True)
    (package_path / "__init__.py").write_text("", encoding="utf-8")
    (package_path / "http_service.py").write_text(
        """
import definitely_missing_dependency
""".strip() + "\n",
        encoding="utf-8",
    )
    venv_python.write_text(
        f'#!/usr/bin/env bash\nexec {verifier.sys.executable} "$@"\n',
        encoding="utf-8",
    )
    venv_python.chmod(venv_python.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
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

    captured_process = process_holder["proc"]
    assert captured_process.command[0] == str(repo_path / ".venv" / "bin" / "python")
    assert captured_process.command[1:3] == ["-m", "travel_plan_permission.http_service"]
    assert captured_process.terminated is True
    assert captured_process.wait_calls == 1


def test_started_tpp_service_starts_known_good_repo_and_tears_down(
    monkeypatch, tmp_path: Path
) -> None:
    repo_path, venv_python = _make_runnable_tpp_repo(tmp_path)
    env = {
        "TPP_REPO_PATH": str(repo_path),
        "TPP_ACCESS_TOKEN": "token",
        "TPP_OIDC_PROVIDER": "google",
    }
    monkeypatch.setattr(verifier, "_wait_for_http", lambda _url: None)
    monkeypatch.setattr(verifier, "_free_local_port", lambda _preferred: 42124)

    with verifier._started_tpp_service(env) as (_base_url, process):
        assert process is not None
        assert process.poll() is None
        process_args = process.args
        assert isinstance(process_args, (list, tuple))
        assert process_args[0] == str(venv_python)

    assert process.poll() is not None


def test_started_tpp_service_readiness_failure_includes_captured_stderr(
    monkeypatch, tmp_path: Path
) -> None:
    repo_path, venv_python = _make_repo_with_venv(tmp_path)

    class FakeProcess:
        def __init__(self, command, **kwargs):
            self.command = command
            stdout_lines = "\n".join(f"stdout-{index}" for index in range(60)) + "\n"
            stderr_lines = "\n".join(f"stderr-{index}" for index in range(60)) + "\n"
            kwargs["stdout"].write(stdout_lines.encode("utf-8"))
            kwargs["stdout"].flush()
            kwargs["stderr"].write(stderr_lines.encode("utf-8"))
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
    assert "stdout_tail" in message
    assert "stderr_tail" in message
    assert "stdout-59" in message
    assert "stderr-59" in message
    assert "stdout-9" not in message
    assert "stderr-9" not in message


def test_started_tpp_service_launch_failure_cleans_temp_files(monkeypatch, tmp_path: Path) -> None:
    repo_path, _ = _make_repo_with_venv(tmp_path)
    created_paths: list[Path] = []
    real_named_temporary_file = verifier.tempfile.NamedTemporaryFile

    def tracked_named_temporary_file(*args, **kwargs):
        temp_file = real_named_temporary_file(*args, **kwargs)
        created_paths.append(Path(temp_file.name))
        return temp_file

    def fail_popen(*_args, **_kwargs):
        raise OSError("cannot start")

    monkeypatch.setattr(verifier.tempfile, "NamedTemporaryFile", tracked_named_temporary_file)
    monkeypatch.setattr(verifier.subprocess, "Popen", fail_popen)
    monkeypatch.setattr(verifier, "_free_local_port", lambda _preferred: 43125)

    with pytest.raises(OSError, match="cannot start"):
        with verifier._started_tpp_service(
            {
                "TPP_REPO_PATH": str(repo_path),
                "TPP_ACCESS_TOKEN": "token",
                "TPP_OIDC_PROVIDER": "google",
            }
        ):
            pass

    assert len(created_paths) == 2
    assert all(not path.exists() for path in created_paths)


def test_tail_file_limits_bytes_before_splitting_lines(tmp_path: Path) -> None:
    output_path = tmp_path / "service.log"
    output_path.write_text("prefix\n" + ("x" * 70000) + "\nlast\n", encoding="utf-8")

    tail = verifier._tail_file(output_path, line_count=2, max_bytes=32)

    assert "prefix" not in tail
    assert "last" in tail
    assert len(tail) < 40


def test_started_tpp_service_readiness_failure_quotes_command(monkeypatch, tmp_path: Path) -> None:
    repo_path = tmp_path / "Travel Plan Permission"
    venv_python = repo_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/usr/bin/env python\n", encoding="utf-8")

    class FakeProcess:
        def __init__(self, _command, **_kwargs):
            pass

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
    monkeypatch.setattr(verifier, "_free_local_port", lambda _preferred: 43126)

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
    assert f"'{venv_python}'" in message
    assert f"'{venv_python}' -m travel_plan_permission.http_service" in message


def test_started_tpp_service_missing_deps_failure_includes_stderr(
    monkeypatch, tmp_path: Path
) -> None:
    repo_path, venv_python = _make_missing_deps_tpp_repo(tmp_path)
    monkeypatch.setattr(verifier, "_free_local_port", lambda _preferred: 43124)

    def fail_readiness_after_process_boot(_url: str) -> None:
        time.sleep(1.0)
        raise verifier.VerificationFailure("not ready")

    monkeypatch.setattr(verifier, "_wait_for_http", fail_readiness_after_process_boot)

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
    assert "ModuleNotFoundError" in message
    assert "definitely_missing_dependency" in message
    assert "stderr_tail" in message


def test_resolve_tpp_interpreter_prefers_repo_venv(tmp_path: Path) -> None:
    repo_path, venv_python = _make_repo_with_venv(tmp_path)
    (repo_path / "uv.lock").write_text("", encoding="utf-8")
    resolved = verifier._resolve_tpp_interpreter(repo_path)
    assert resolved == [str(venv_python)]


def test_resolve_tpp_interpreter_uses_uv_when_lock_present(monkeypatch, tmp_path: Path) -> None:
    repo_path = tmp_path / "Travel-Plan-Permission"
    repo_path.mkdir(parents=True)
    (repo_path / "uv.lock").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        verifier.shutil, "which", lambda command: "/usr/bin/uv" if command == "uv" else None
    )
    resolved = verifier._resolve_tpp_interpreter(repo_path)
    assert resolved == ["uv", "run", "--directory", str(repo_path), "python"]


def test_resolve_tpp_interpreter_fails_fast_when_no_venv_or_uv(monkeypatch, tmp_path: Path) -> None:
    repo_path = tmp_path / "Travel-Plan-Permission"
    repo_path.mkdir(parents=True)
    monkeypatch.setattr(verifier.shutil, "which", lambda _command: None)
    with pytest.raises(verifier.VerificationFailure) as exc_info:
        verifier._resolve_tpp_interpreter(repo_path)
    message = str(exc_info.value)
    assert str(repo_path / ".venv" / "bin" / "python") in message
    assert f"uv run --directory {repo_path} python" in message
