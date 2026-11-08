"""The TestClient precondition must fail explicitly and close its probe sockets."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests import runtime_requirements


@pytest.fixture
def probe_sockets(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    sender, receiver = MagicMock(), MagicMock()
    receiver.recv.return_value = b"x"
    monkeypatch.setattr(runtime_requirements.socket, "socketpair", lambda: (sender, receiver))
    return sender, receiver


def test_socket_probe_allows_available_runtime(probe_sockets: tuple[MagicMock, MagicMock]) -> None:
    sender, receiver = probe_sockets

    runtime_requirements.require_testclient_socket_io()

    sender.settimeout.assert_called_once_with(1)
    receiver.settimeout.assert_called_once_with(1)
    sender.sendall.assert_called_once_with(b"x")
    receiver.recv.assert_called_once_with(1)
    sender.__exit__.assert_called_once()
    receiver.__exit__.assert_called_once()


@pytest.mark.parametrize("stage", ["settimeout", "sendall", "recv", "empty_read"])
def test_socket_probe_exits_nonzero_and_closes_sockets(
    probe_sockets: tuple[MagicMock, MagicMock], stage: str
) -> None:
    sender, receiver = probe_sockets
    if stage == "empty_read":
        receiver.recv.return_value = b""
    else:
        target = receiver if stage == "recv" else sender
        getattr(target, stage).side_effect = PermissionError(1, "Operation not permitted")

    with pytest.raises(pytest.exit.Exception, match="local socketpair I/O failed") as raised:
        runtime_requirements.require_testclient_socket_io()

    assert raised.value.returncode == pytest.ExitCode.TESTS_FAILED
    assert "not a passing test run" in str(raised.value)
    sender.__exit__.assert_called_once()
    receiver.__exit__.assert_called_once()


def test_socket_creation_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied_socketpair() -> None:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(runtime_requirements.socket, "socketpair", denied_socketpair)

    with pytest.raises(pytest.exit.Exception, match="Operation not permitted") as raised:
        runtime_requirements.require_testclient_socket_io()

    assert raised.value.returncode == pytest.ExitCode.TESTS_FAILED


@pytest.mark.parametrize("denied", [False, True])
def test_app_fixture_checks_runtime_before_test_body(tmp_path: Path, denied: bool) -> None:
    (tmp_path / "conftest.py").write_text(
        "import socket\n"
        "from unittest.mock import MagicMock\n"
        "sender, receiver = MagicMock(), MagicMock()\n"
        "receiver.recv.return_value = b'x'\n"
        + (
            "sender.sendall.side_effect = PermissionError(1, 'Operation not permitted')\n"
            if denied
            else ""
        )
        + "socket.socketpair = lambda: (sender, receiver)\n",
        encoding="utf-8",
    )
    (tmp_path / "test_example.py").write_text(
        "from pathlib import Path\n"
        "def test_body():\n"
        "    Path('body-ran').write_text('yes')\n",
        encoding="utf-8",
    )
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "tests.app.conftest", "-q"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTEST_ADDOPTS": "",
            "PYTHONPATH": os.pathsep.join(filter(None, [str(root), os.getenv("PYTHONPATH")])),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == (
        pytest.ExitCode.TESTS_FAILED if denied else pytest.ExitCode.OK
    ), output
    assert (tmp_path / "body-ran").exists() is not denied
    if denied:
        assert "TestClient runtime unavailable" in output
    else:
        assert "1 passed" in output
