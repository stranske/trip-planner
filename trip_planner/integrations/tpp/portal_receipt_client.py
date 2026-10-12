"""Owner-authenticated reads of the accepted producer's portal receipt contract."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib import error, parse, request

from .client import TPPConfigurationError, TPPContractError, TPPTransportError
from .portal_handoff import portal_action_url
from .portal_receipt import PortalReceiptBinding


@dataclass(frozen=True)
class PortalOwnerIdentity:
    """Identity resolved by a trusted server bridge, never by browser parameters.

    namespace identifies the validated issuer/audience/provider combination.
    The bridge must resolve a traveler credential, not the shared service bearer.
    """

    namespace: str
    subject: str
    authorization: str = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.namespace or not self.subject:
            raise TPPConfigurationError("The portal traveler identity is not configured.")
        if (
            not self.authorization.startswith("Bearer ")
            or not self.authorization[7:].strip()
            or any(character in self.authorization for character in "\r\n")
        ):
            raise TPPConfigurationError("The portal traveler authorization is invalid.")

    def owner_binding(self) -> dict[str, str]:
        return {"namespace": self.namespace, "subject": self.subject}


class PortalReceiptReadError(TPPTransportError):
    """A failed observation, distinct from a successful prepared receipt."""

    def __init__(self, observation_status: str) -> None:
        super().__init__("The portal receipt could not be observed.", status_code=502)
        self.observation_status = observation_status


class _RejectRedirects(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Owner authorization must never follow a redirect to another origin.
        return None


class OwnerPortalReceiptClient:
    """Read from a fixed origin using an explicitly supplied trusted identity bridge.

    The resolver receives the authenticated local account ID. It must use an
    established server-side identity mapping or exchange; this client provides
    neither anonymous subject minting nor a shared-service fallback.
    """

    def __init__(self, identity_resolver: Callable[[str], PortalOwnerIdentity]) -> None:
        self._identity_resolver = identity_resolver
        self._opener = request.build_opener(_RejectRedirects())

    def resolve_owner(self, user_id: str) -> PortalOwnerIdentity:
        return self._identity_resolver(user_id)

    def read_receipt(self, *, identity: PortalOwnerIdentity, binding: PortalReceiptBinding) -> Any:
        origin = portal_action_url().removesuffix("/portal/handoff")
        path = parse.quote(binding.handoff_id, safe="")
        query = parse.urlencode({"snapshot_version": binding.snapshot_version})
        outgoing = request.Request(
            f"{origin}/api/planner/portal-handoffs/{path}?{query}",
            headers={"Authorization": identity.authorization, "Accept": "application/json"},
            method="GET",
        )
        try:
            with self._opener.open(outgoing, timeout=15) as response:
                if response.status != 200:
                    raise PortalReceiptReadError("unavailable")
                body = response.read(65_537)
        except error.HTTPError as failure:
            status = {401: "unauthorized", 403: "unauthorized", 404: "not_found", 409: "stale"}
            failure.close()
            raise PortalReceiptReadError(status.get(failure.code, "unavailable")) from None
        except (OSError, error.URLError):
            # Upstream errors can include credentials or private response data.
            raise PortalReceiptReadError("unavailable") from None
        if len(body) > 65_536:
            raise TPPContractError("Malformed TPP portal receipt contract.")
        try:
            return json.loads(body)
        except (ValueError, UnicodeError):
            raise TPPContractError("Malformed TPP portal receipt contract.") from None
