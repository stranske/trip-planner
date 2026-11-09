"""Exercise interpreter changes using real venv launchers and local ensurepip."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
import venv
from pathlib import Path

import pytest


@pytest.mark.parametrize("reuse_system_packages", [False, True], ids=["fresh", "previously-shared"])
def test_create_dev_venv_isolates_dependencies(tmp_path: Path, reuse_system_packages: bool) -> None:
    """Acceptance must use installed dev extras, never packages from the base Python."""
    destination = tmp_path / "dedicated environment"
    if reuse_system_packages:
        venv.EnvBuilder(with_pip=False, system_site_packages=True).create(destination)

    script = Path(__file__).resolve().parents[2] / "scripts/create_dev_venv.py"
    setup = subprocess.run(
        [sys.executable, str(script), str(destination)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert setup.returncode == 0, setup.stdout + setup.stderr
    python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    probe = subprocess.run(
        [
            python,
            "-I",
            "-c",
            (
                "import json, pip, sys; "
                "print(json.dumps({'prefix': sys.prefix, 'pip': pip.__file__, 'path': sys.path}))"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    runtime = json.loads(probe.stdout)
    assert Path(runtime["prefix"]).resolve() == destination.resolve()
    assert Path(runtime["pip"]).resolve().is_relative_to(destination.resolve())
    base_paths = sysconfig.get_paths(vars={"base": sys.base_prefix, "platbase": sys.base_prefix})
    imported_paths = {Path(path).resolve() for path in runtime["path"]}
    for key in ("purelib", "platlib"):
        assert Path(base_paths[key]).resolve() not in imported_paths


@pytest.mark.parametrize("changed_interpreter", [False, True])
@pytest.mark.parametrize("missing_metadata", [False, True], ids=["metadata", "missing-metadata"])
def test_create_dev_venv_replaces_stale_interpreter_only(
    tmp_path: Path, changed_interpreter: bool, missing_metadata: bool
) -> None:
    destination = tmp_path / "development environment"
    venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt").create(destination)
    if missing_metadata:
        (destination / "pyvenv.cfg").unlink()
    marker = destination / "installed-package-marker"
    marker.write_text("keep for the same interpreter", encoding="utf-8")
    python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if changed_interpreter:
        if os.name != "nt":
            # A reused launcher can remain stale even if metadata names the
            # selected Python or was lost during interrupted setup.
            previous = tmp_path / "previous-python"
            previous.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
            previous.chmod(0o755)
            python.unlink()
            python.symlink_to(previous)
        else:
            python.write_bytes(b"broken Python launcher")

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
    assert (
        Path(json.loads(probe.stdout)).resolve()
        == Path(getattr(sys, "_base_executable", sys.executable)).resolve()
    )
    assert marker.exists() is not changed_interpreter
