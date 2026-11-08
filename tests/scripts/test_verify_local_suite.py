"""Exercise committed-tree verification against small real repositories and pytest."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify_local_suite import verify


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "source with spaces"
    root.mkdir()
    git(root, "init", "-q")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "verification-fixture"\nrequires-python = ">=3.13,<3.15"\n',
        encoding="utf-8",
    )
    (root / ".python-version").write_text("3.14\n", encoding="utf-8")
    (root / "test_example.py").write_text(
        "def test_pass():\n    assert True\n"
        "def test_failure():\n    assert False, 'retained failure traceback'\n",
        encoding="utf-8",
    )
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Verification Test",
        "-c",
        "user.email=verification@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    return root


def test_failed_suite_preserves_unfiltered_result_and_committed_tree(
    repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit = git(repository, "rev-parse", "HEAD")
    # Neither dirty working files nor inherited exclusions may create a false pass.
    (repository / "test_example.py").write_text("def test_pass():\n    pass\n", encoding="utf-8")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k test_pass")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nonexistent"))
    output = tmp_path / "failure evidence"

    assert verify(repository, output, sys.executable, (commit,)) == 1

    record = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert record["commit"] == commit
    assert record["verified_ancestors"] == [commit]
    assert record["command"] == [sys.executable, "-m", "pytest"]
    assert record["exit_status"] == 1
    assert record["requires_python"] == ">=3.13,<3.15"
    assert record["preferred_python"] == "3.14"
    assert record["finished_at"] >= record["started_at"]
    log = Path(record["log"]).read_text(encoding="utf-8")
    assert "test_example.py::test_failure" in log
    assert "retained failure traceback" in log
    assert "1 failed, 1 passed" in log


def test_pass_and_existing_evidence_is_not_overwritten(repository: Path, tmp_path: Path) -> None:
    (repository / "test_example.py").write_text("def test_pass():\n    pass\n", encoding="utf-8")
    git(repository, "add", ".")
    git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "pass",
    )
    output = tmp_path / "pass"

    assert verify(repository, output, sys.executable) == 0

    evidence = (output / "result.json").read_bytes()
    assert json.loads(evidence)["exit_status"] == 0
    with pytest.raises(FileExistsError):
        verify(repository, output, sys.executable)
    assert (output / "result.json").read_bytes() == evidence


def test_unsupported_runtime_is_rejected_before_pytest(repository: Path, tmp_path: Path) -> None:
    output = tmp_path / "unsupported"
    # The runtime probe is real, while metadata makes this interpreter unsupported.
    (repository / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=99"\n', encoding="utf-8"
    )
    git(repository, "add", ".")
    git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "unsupported",
    )

    with pytest.raises(ValueError, match="does not satisfy >=99"):
        verify(repository, output, sys.executable)

    assert not (output / "pytest.log").exists()
    assert not (output / "result.json").exists()


@pytest.mark.parametrize("exists", [False, True])
def test_missing_required_merge_is_rejected_before_pytest(
    repository: Path, tmp_path: Path, exists: bool
) -> None:
    output = tmp_path / "missing-merge"
    ancestor = "missing-merge"
    if exists:
        # A real commit object is insufficient: it must be an ancestor of HEAD.
        ancestor = git(
            repository,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit-tree",
            "HEAD^{tree}",
            "-m",
            "unrelated root",
        )

    with pytest.raises(subprocess.CalledProcessError):
        verify(repository, output, sys.executable, (ancestor,))

    assert not (output / "pytest.log").exists()
    assert not (output / "result.json").exists()
