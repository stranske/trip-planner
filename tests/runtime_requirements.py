"""Report local runtime restrictions before entering TestClient's blocking portal."""

import socket

import pytest


def require_testclient_socket_io() -> None:
    """Abort with a failure when asyncio's local wakeup transport is unavailable."""
    operation = "create socketpair"
    try:
        sender, receiver = socket.socketpair()
        with sender, receiver:
            operation = "set sender timeout"
            sender.settimeout(1)
            operation = "set receiver timeout"
            receiver.settimeout(1)
            operation = "send wakeup byte"
            sender.sendall(b"x")
            operation = "receive wakeup byte"
            if receiver.recv(1) != b"x":
                raise OSError("socketpair did not deliver the wakeup byte")
    except OSError as exc:
        pytest.exit(
            "TestClient runtime unavailable: local socketpair I/O failed "
            f"during {operation} ({type(exc).__name__}: {exc}). "
            "Run the unchanged suite in an environment permitting local "
            "socket operations. This is an environment failure, not a passing test run.",
            returncode=pytest.ExitCode.TESTS_FAILED,
        )
