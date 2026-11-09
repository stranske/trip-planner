"""Exercise interpreter changes using real venv launchers and local ensurepip."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest


@pytest.mark.parametrize("changed_interpreter", [False, True])
def test_create_dev_venv_replaces_stale_interpreter_only(
    tmp_path: Path, changed_interpreter: bool
) -> None:
    destination = tmp_path / "development environment"
    venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt").create(destination)
    marker = destination / "installed-package-marker"
    marker.write_text("keep for the same interpreter", encoding="utf-8")
    python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if changed_interpreter:
        if os.name != "nt":
            # A second `python -m venv` updates pyvenv.cfg but can leave the
            # old launcher. Its metadata already names the selected Python.
            previous = tmp_path / "previous-python"
            previous.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
            previous.chmod(0o755)
            python.unlink()
            python.symlink_to(previous)
        else:
            python.unlink()

    script = Path(__file__).resolve().parents[2] / "scripts/create_dev_venv.py"
    setup = subprocess.run(
        [sys.executable, str(script), str(destination)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert setup.returncode == 0, setup.stdout + setup.stderr
    probe = subprocess.run(
        [python, "-c", "import json, pip, sys; print(json.dumps(sys._base_executable))"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    assert Path(json.loads(probe.stdout)).resolve() == Path(sys._base_executable).resolve()
    assert marker.exists() is not changed_interpreter
