"""Exercise the local bootstrap recipe without downloading dependencies."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("pip_status", [0, 23])
def test_install_provisions_dev_environment_before_frontend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pip_status: int
) -> None:
    """Keep omitted-from-lock dev packages installed, and propagate pip failures."""
    root = Path(__file__).resolve().parents[1]
    shutil.copyfile(root / "Makefile", tmp_path / "Makefile")
    commands = tmp_path / "commands.jsonl"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Substitute only the external installers; execute the actual Makefile recipe.
    # The Python double creates the venv executable so an accidental use of the
    # system pip can be distinguished from the intended dedicated environment.
    installer = f"#!{sys.executable}\n" + """\
import json
import os
import shutil
import sys
from pathlib import Path

with Path(os.environ["BOOTSTRAP_TEST_COMMANDS"]).open("a") as stream:
    stream.write(json.dumps(sys.argv) + "\\n")
if sys.argv[1:3] == ["-m", "venv"]:
    target = Path(sys.argv[3]) / "bin" / "python"
    target.parent.mkdir(parents=True)
    shutil.copyfile(__file__, target)
    target.chmod(0o755)
elif sys.argv[1:4] == ["-m", "pip", "install"]:
    sys.exit(int(os.environ["BOOTSTRAP_TEST_PIP_STATUS"]))
"""
    for name in ("python", "npm"):
        path = bin_dir / name
        path.write_text(installer, encoding="utf-8")
        path.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("BOOTSTRAP_TEST_COMMANDS", str(commands))
    monkeypatch.setenv("BOOTSTRAP_TEST_PIP_STATUS", str(pip_status))
    # Do not let inherited make flags turn the recipe into a dry run or ignore errors.
    for name in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES"):
        monkeypatch.delenv(name, raising=False)

    result = subprocess.run(
        ["make", "install"], cwd=tmp_path, capture_output=True, text=True, check=False, timeout=20
    )

    calls = [json.loads(line) for line in commands.read_text(encoding="utf-8").splitlines()]
    assert calls[0][1:] == ["-m", "venv", ".venv"]
    assert len(calls) >= 2, result.stdout + result.stderr
    assert (tmp_path / calls[1][0]).resolve() == tmp_path / ".venv/bin/python"
    # baseline_kit is intentionally absent from the lock: extras must be resolved
    # alongside the lock in this same pip call, rather than relying on global packages.
    assert calls[1][1:] == ["-m", "pip", "install", "-r", "requirements.lock", "-e", ".[dev]"]
    if pip_status:
        assert result.returncode != 0, result.stdout + result.stderr
        assert len(calls) == 2, "Frontend setup must stop when Python provisioning fails"
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(calls) == 3
        assert Path(calls[2][0]).name == "npm"
        assert calls[2][1:] == ["--prefix", "frontend", "ci"]


@pytest.mark.parametrize("pytest_status", [0, 17])
def test_make_test_uses_provisioned_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pytest_status: int
) -> None:
    """Run unrestricted pytest in the installed venv without requiring activation."""
    root = Path(__file__).resolve().parents[1]
    shutil.copyfile(root / "Makefile", tmp_path / "Makefile")
    venv_python = tmp_path / ".venv/bin/python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "print(json.dumps(sys.argv))\n"
        f"sys.exit({pytest_status})\n",
        encoding="utf-8",
    )
    venv_python.chmod(0o755)
    system_bin = tmp_path / "system-bin"
    system_bin.mkdir()
    system_python = system_bin / "python"
    system_python.write_text(f"#!{sys.executable}\nraise SystemExit(99)\n", encoding="utf-8")
    system_python.chmod(0o755)
    monkeypatch.setenv("PATH", str(system_bin) + os.pathsep + os.environ["PATH"])
    for name in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES"):
        monkeypatch.delenv(name, raising=False)

    result = subprocess.run(
        ["make", "test"], cwd=tmp_path, capture_output=True, text=True, check=False, timeout=20
    )

    calls = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("[")]
    assert len(calls) == 1, result.stdout + result.stderr
    assert (tmp_path / calls[0][0]).resolve() == venv_python
    assert calls[0][1:] == ["-m", "pytest"]
    assert (result.returncode == 0) == (pytest_status == 0), result.stdout + result.stderr
