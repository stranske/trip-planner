"""Exercise the portal gate against real temporary Git revisions."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.integration.portal_contract_checkout import resolve_portal_contract_checkout


def _git(checkout: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(checkout), *arguments],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()


@pytest.fixture
def producer_checkout(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "src" / "travel_plan_permission" / "http_service.py"
    source.parent.mkdir(parents=True)
    source.write_text('"""A producer source marker for checkout verification."""\n')
    _git(tmp_path, "init", "--quiet")
    _git(tmp_path, "add", "src")
    _git(
        tmp_path,
        "-c",
        "user.name=Portal Contract Test",
        "-c",
        "user.email=portal-contract@example.test",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--quiet",
        "-m",
        "Producer baseline",
    )
    return tmp_path, _git(tmp_path, "rev-parse", "HEAD")


def test_optional_local_contract_can_skip_without_a_checkout() -> None:
    assert resolve_portal_contract_checkout({}) is None


def test_pinned_contract_cannot_skip_without_a_checkout() -> None:
    with pytest.raises(pytest.UsageError, match="TPP_REPO_PATH is required"):
        resolve_portal_contract_checkout({"TPP_PINNED_REF": "a" * 40})


def test_explicit_checkout_must_contain_portal_source(tmp_path: Path) -> None:
    with pytest.raises(pytest.UsageError, match="real TPP portal source"):
        resolve_portal_contract_checkout({"TPP_REPO_PATH": str(tmp_path)})


def test_local_checkout_does_not_require_a_pin(producer_checkout: tuple[Path, str]) -> None:
    checkout, _ = producer_checkout
    assert resolve_portal_contract_checkout({"TPP_REPO_PATH": str(checkout)}) == checkout


def test_contract_accepts_the_exact_producer_pin(producer_checkout: tuple[Path, str]) -> None:
    checkout, revision = producer_checkout
    assert (
        resolve_portal_contract_checkout(
            {"TPP_REPO_PATH": str(checkout), "TPP_PINNED_REF": revision}
        )
        == checkout
    )


def test_contract_rejects_a_different_producer_revision(
    producer_checkout: tuple[Path, str],
) -> None:
    checkout, revision = producer_checkout
    _git(
        checkout,
        "-c",
        "user.name=Portal Contract Test",
        "-c",
        "user.email=portal-contract@example.test",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "Unaccepted producer revision",
    )
    with pytest.raises(pytest.UsageError, match="does not match TPP_PINNED_REF"):
        resolve_portal_contract_checkout(
            {"TPP_REPO_PATH": str(checkout), "TPP_PINNED_REF": revision}
        )


@pytest.mark.parametrize("pin", ["main", "a" * 39, "A" * 40, "a" * 41, "--help"])
def test_contract_rejects_non_sha_pins(producer_checkout: tuple[Path, str], pin: str) -> None:
    checkout, _ = producer_checkout
    with pytest.raises(pytest.UsageError, match="full lowercase commit SHA"):
        resolve_portal_contract_checkout({"TPP_REPO_PATH": str(checkout), "TPP_PINNED_REF": pin})


def test_contract_cannot_verify_an_unversioned_source_directory(tmp_path: Path) -> None:
    source = tmp_path / "src" / "travel_plan_permission" / "http_service.py"
    source.parent.mkdir(parents=True)
    source.touch()
    with pytest.raises(pytest.UsageError, match="Cannot verify"):
        resolve_portal_contract_checkout(
            {"TPP_REPO_PATH": str(tmp_path), "TPP_PINNED_REF": "a" * 40}
        )


def test_contract_rejects_a_source_directory_inside_another_checkout(
    producer_checkout: tuple[Path, str],
) -> None:
    checkout, revision = producer_checkout
    nested = checkout / "nested"
    source = nested / "src" / "travel_plan_permission" / "http_service.py"
    source.parent.mkdir(parents=True)
    source.touch()
    with pytest.raises(pytest.UsageError, match="root of the pinned Git checkout"):
        resolve_portal_contract_checkout({"TPP_REPO_PATH": str(nested), "TPP_PINNED_REF": revision})
