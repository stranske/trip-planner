"""Resolve the optional producer checkout, enforcing an explicitly requested pin."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest


def verify_portal_contract_imports(checkout: Path) -> None:
    """Reject cached or newly loaded TPP dependencies from another source tree.

    Adding the checkout to sys.path does not replace modules already in
    sys.modules. Check the entire producer namespace before and after importing
    its app, including package search paths used to resolve later dependencies.
    """

    source = (checkout / "src").resolve()
    for name, module in sys.modules.copy().items():
        if module is None or not (
            name == "travel_plan_permission" or name.startswith("travel_plan_permission.")
        ):
            continue
        paths = list(getattr(module, "__path__", ()))
        filename = getattr(module, "__file__", None)
        if filename is not None:
            paths.append(filename)
        if not paths:
            raise pytest.UsageError(f"Cannot verify pinned TPP module {name} source.")
        if any(not Path(path).resolve().is_relative_to(source) for path in paths):
            raise pytest.UsageError(f"Module {name} was loaded outside the pinned TPP checkout.")


def resolve_portal_contract_checkout(environment: Mapping[str, str]) -> Path | None:
    """Allow optional local runs; never skip or use a different revision for a pinned run."""

    repo_path = environment.get("TPP_REPO_PATH", "").strip()
    pinned_ref = environment.get("TPP_PINNED_REF", "").strip()
    if not repo_path:
        if pinned_ref:
            raise pytest.UsageError("TPP_REPO_PATH is required when TPP_PINNED_REF is set.")
        return None

    checkout = Path(repo_path).resolve()
    source = checkout / "src" / "travel_plan_permission" / "http_service.py"
    if not source.is_file():
        raise pytest.UsageError("TPP_REPO_PATH must contain the real TPP portal source.")
    if not pinned_ref:
        return checkout
    if not re.fullmatch(r"[0-9a-f]{40}", pinned_ref):
        raise pytest.UsageError("TPP_PINNED_REF must be a full lowercase commit SHA.")

    try:
        root = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        resolved_ref = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        source_changes = subprocess.run(
            [
                "git",
                "-C",
                str(checkout),
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                "src",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as error:
        raise pytest.UsageError("Cannot verify the pinned TPP checkout revision.") from error
    if Path(root).resolve() != checkout:
        raise pytest.UsageError("TPP_REPO_PATH must be the root of the pinned Git checkout.")
    if resolved_ref != pinned_ref:
        raise pytest.UsageError(
            f"TPP checkout revision {resolved_ref} does not match TPP_PINNED_REF {pinned_ref}."
        )
    if source_changes:
        raise pytest.UsageError("The pinned TPP checkout must contain unmodified producer source.")
    return checkout
