"""Resolve the optional producer checkout, enforcing an explicitly requested pin."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest


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
    except (OSError, subprocess.SubprocessError) as error:
        raise pytest.UsageError("Cannot verify the pinned TPP checkout revision.") from error
    if Path(root).resolve() != checkout:
        raise pytest.UsageError("TPP_REPO_PATH must be the root of the pinned Git checkout.")
    if resolved_ref != pinned_ref:
        raise pytest.UsageError(
            f"TPP checkout revision {resolved_ref} does not match TPP_PINNED_REF {pinned_ref}."
        )
    return checkout
