"""Create the development environment with the selected Python interpreter."""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path


def create_dev_venv(destination: Path) -> None:
    """Rebuild an existing venv only when its base interpreter has changed."""
    clear = False
    if (destination / "pyvenv.cfg").is_file():
        python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        # Reusing a venv with `python -m venv` can leave bin/python linked to
        # the previous interpreter, so inspect its runtime rather than its cfg.
        try:
            probe = subprocess.run(
                [python, "-c", "import sys; print(sys._base_executable)"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            executable = probe.stdout.strip()
            clear = (
                probe.returncode != 0
                or not executable
                or Path(executable).resolve()
                != Path(getattr(sys, "_base_executable", sys.executable)).resolve()
            )
        except (OSError, subprocess.TimeoutExpired):
            clear = True
    venv.EnvBuilder(with_pip=True, symlinks=os.name != "nt", clear=clear).create(destination)


if __name__ == "__main__":
    create_dev_venv(Path(sys.argv[1]))
