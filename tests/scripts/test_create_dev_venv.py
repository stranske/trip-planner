"""Exercise interpreter changes using real venv launchers and local ensurepip."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import sysconfig
import venv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import create_dev_venv as bootstrap


def test_create_dev_venv_recovers_from_probe_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stalled launcher must be replaced before dependencies can be installed."""
    destination = tmp_path / "stalled environment"
    venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt").create(destination)
    marker = destination / "old-installed-package"
    marker.write_text("remove when rebuilding", encoding="utf-8")
    python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    probe = Mock(side_effect=subprocess.TimeoutExpired(cmd=[python], timeout=10))
    # Substitute only the bootstrap probe; venv/ensurepip still run real processes.
    monkeypatch.setattr(
        bootstrap,
        "subprocess",
        SimpleNamespace(run=probe, TimeoutExpired=subprocess.TimeoutExpired),
    )

    bootstrap.create_dev_venv(destination)

    probe.assert_called_once()
    assert not marker.exists(), "The timed-out environment must be rebuilt"
    recovered = subprocess.run(
        [
            python,
            "-I",
            "-c",
            "import json, pip, sys; print(json.dumps([sys.prefix, pip.__file__]))",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    prefix, pip_path = json.loads(recovered.stdout)
    assert Path(prefix).resolve() == destination.resolve()
    assert Path(pip_path).resolve().is_relative_to(destination.resolve())


def test_create_dev_venv_switches_supported_python_version(tmp_path: Path) -> None:
    """A real 3.13/3.14 switch must remove old dependencies and bootstrap local pip."""
    other_version = "3.13" if sys.version_info[:2] == (3, 14) else "3.14"
    other_python = shutil.which(f"python{other_version}")
    if other_python is None:
        pytest.skip(f"Python {other_version} is required for the interpreter migration check")

    destination = tmp_path / "development environment"
    previous = subprocess.run(
        [other_python, "-I", "-m", "venv", "--without-pip", str(destination)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert previous.returncode == 0, previous.stdout + previous.stderr
    python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    old_runtime = subprocess.run(
        [
            python,
            "-I",
            "-c",
            (
                "import json, sys, sysconfig; "
                "print(json.dumps([list(sys.version_info[:2]), sysconfig.get_path('purelib')]))"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert old_runtime.returncode == 0, old_runtime.stdout + old_runtime.stderr
    old_version, old_site = json.loads(old_runtime.stdout)
    assert old_version != list(sys.version_info[:2]), "The migration needs distinct runtimes"
    old_package = Path(old_site) / "previous_runtime_package.py"
    old_package.write_text("INSTALLED = True\n", encoding="utf-8")

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
        [
            python,
            "-I",
            "-c",
            (
                "import importlib.util, json, pip, sys; "
                "print(json.dumps({'version': list(sys.version_info[:2]), 'prefix': sys.prefix, "
                "'pip': pip.__file__, 'old_package': "
                "importlib.util.find_spec('previous_runtime_package') is not None}))"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    runtime = json.loads(probe.stdout)
    assert runtime["version"] == list(sys.version_info[:2])
    assert Path(runtime["prefix"]).resolve() == destination.resolve()
    assert Path(runtime["pip"]).resolve().is_relative_to(destination.resolve())
    assert not runtime["old_package"]
    assert not old_package.exists(), "Rebuilding must remove the previous minor version's packages"


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
    assert (
        "include-system-site-packages = false"
        in (destination / "pyvenv.cfg").read_text(encoding="utf-8").splitlines()
    )


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
