"""Resolve pre-provisioned individual TPP credentials from a private server file."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from .client import TPPConfigurationError
from .portal_receipt_client import OwnerPortalReceiptClient, PortalOwnerIdentity

IDENTITIES_FILE_ENV = "TRIP_PLANNER_TPP_IDENTITIES_FILE"


def configured_portal_client() -> OwnerPortalReceiptClient | None:
    """Install the runtime bridge only when an administrator configured its store.

    Tokens must already have been issued for the mapped individual by TPP's
    trusted issuer. This bridge never mints subjects or uses the service bearer.
    The file is re-read on each resolution so revocation/rotation takes effect.
    """
    filename = os.environ.get(IDENTITIES_FILE_ENV, "").strip()
    if not filename:
        return None

    def resolve(user_id: str) -> PortalOwnerIdentity:
        descriptor = None
        try:
            path = Path(filename)
            if not path.is_absolute():
                raise ValueError("absolute path required")
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_size > 1_048_576
            ):
                raise ValueError("private owner-controlled file required")
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                descriptor = None
                data = json.load(handle)
            if (
                not isinstance(data, dict)
                or data.get("schema_version") != "tpp-owner-identities/v1"
            ):
                raise ValueError("invalid identity store")
            entry = data["users"][user_id]
            if not isinstance(entry, dict) or set(entry) != {
                "namespace",
                "subject",
                "authorization",
            }:
                raise ValueError("invalid identity entry")
            if not all(isinstance(value, str) for value in entry.values()):
                raise ValueError("invalid identity entry")
            identity = PortalOwnerIdentity(**entry)
            shared = os.environ.get("TPP_ACCESS_TOKEN", "").strip()
            if shared and identity.authorization == f"Bearer {shared}":
                raise ValueError("shared service token forbidden")
            return identity
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise TPPConfigurationError("Individual portal identity is unavailable.") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)

    return OwnerPortalReceiptClient(resolve)
