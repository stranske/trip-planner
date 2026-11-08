"""Run the unrestricted local suite in an isolated checkout and retain its evidence.

Uses the selected interpreter's existing development environment; installs nothing.
The output directory must be new so previous verification artifacts stay intact.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version


def verify(source: Path, output: Path, interpreter: str, ancestors: tuple[str, ...] = ()) -> int:
    """Record an exact committed-tree run; return pytest's failure status unchanged."""
    source, output = source.resolve(), output.resolve()
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_") and key not in {"PYTEST_ADDOPTS", "PYTHONPATH"}
    }

    def git(root: Path, *args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], env=env, text=True, stderr=subprocess.PIPE
        ).strip()

    commit = git(source, "rev-parse", "--verify", "HEAD")
    output.mkdir(parents=True, exist_ok=False)
    checkout = output / "checkout"
    git(source, "clone", "--shared", "--no-hardlinks", "--no-checkout", str(source), str(checkout))
    git(checkout, "checkout", "--detach", commit)
    verified_ancestors = []
    for ancestor in ancestors:
        resolved = git(
            checkout, "rev-parse", "--verify", "--end-of-options", f"{ancestor}^{{commit}}"
        )
        git(checkout, "merge-base", "--is-ancestor", resolved, "HEAD")
        verified_ancestors.append(resolved)

    with (checkout / "pyproject.toml").open("rb") as stream:
        requirement = tomllib.load(stream)["project"]["requires-python"]
    preferred = (checkout / ".python-version").read_text(encoding="utf-8").strip()
    runtime = json.loads(
        subprocess.check_output(
            [
                interpreter,
                "-c",
                (
                    "import json, platform, sys; "
                    "print(json.dumps({'version': platform.python_version(), "
                    "'executable': sys.executable, 'implementation': platform.python_implementation()}))"
                ),
            ],
            cwd=checkout,
            env=env,
            text=True,
        )
    )
    if Version(runtime["version"]) not in SpecifierSet(requirement):
        raise ValueError(f"Python {runtime['version']} does not satisfy {requirement}")
    command = [runtime["executable"], "-m", "pytest"]
    record = {
        "commit": commit,
        "verified_ancestors": verified_ancestors,
        "runtime": runtime,
        "requires_python": requirement,
        "preferred_python": preferred,
        "command": command,
        "cwd": str(checkout),
        "log": str(output / "pytest.log"),
        "started_at": datetime.now(UTC).isoformat(),
        "exit_status": None,
    }
    evidence = output / "result.json"
    evidence.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    with (output / "pytest.log").open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(
                command, cwd=checkout, env=env, stdout=log, stderr=subprocess.STDOUT, check=False
            )
            status = result.returncode if result.returncode >= 0 else 128 - result.returncode
        except KeyboardInterrupt:
            status = 130
    record.update(exit_status=status, finished_at=datetime.now(UTC).isoformat())
    evidence.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Full suite exited {status}; evidence: {evidence}; output: {record['log']}")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--require-ancestor", action="append", default=[])
    args = parser.parse_args()
    try:
        return verify(args.source, args.output, args.python, tuple(args.require_ancestor))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Verification setup failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
