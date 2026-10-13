# Authenticated approval handoff

The production `create_app()` installs an individual owner credential resolver when
`TRIP_PLANNER_TPP_IDENTITIES_FILE` names an absolute, regular, non-symlink server file
owned by the runtime user with no group/other access (mode 0600). Provision it outside
the repository, frontend assets and database exports. This POSIX file bridge requires
no shared service bearer and never creates a traveler subject from a browser hint.

The private JSON format is `{"schema_version":"tpp-owner-identities/v1","users":{...}}`.
Each key is an existing local account ID. Each value contains exactly `namespace`,
`subject`, and `authorization` (`Bearer <individually issued credential>`). The mapping
must be provisioned from the trusted producer issuer: use its verified subject and
provider for bootstrap identities, or its verified issuer/audience namespace for OIDC.
Do not use `TPP_ACCESS_TOKEN`; static service authentication cannot own these receipts.
Never commit credentials. The resolver rereads the file for rotation/revocation and
fails closed for an unknown account, bad file, or a shared-service-token substitution.
The producer performs its normal authentication, expiry and permissions checks.

`TPP_PORTAL_BASE_URL` sets the fixed producer origin. The browser cannot select it,
supply identity, replace saved trip/quote facts, or submit/approve with its view-only
capability. Missing configuration retains the legacy preparation surface, which does
not claim an authenticated receipt or decision; deployment provisioning is separate
from this component proof. No deployed identity-provider acceptance is claimed here.

The Policy tab collects explicit missing traveler facts, never defaults an attestation,
and sends the bounded `traveler_answers` object through the authenticated consumer
route. Saved facts remain authoritative. The producer freshly validates the complete
form/policy. The producer version binds both the saved snapshot and these answers;
retries reuse them, and replacement answers require a new policy-bound preparation.
A reopened handoff uses the stored answers rather than asking the traveler to recreate
them. Tokens stay out of URLs, public workspace state and persisted consumer metadata.

The real cross-repo test starts the pinned producer on a loopback HTTP socket and uses
the production consumer factory with its configured file bridge and a real consumer
session. It proves approval and rejection, traveler-only submission, manager-only
decision, correlated workspace status, consumer restart and idempotent replay. The
browser view capability alone fails submission. No auth dependency or producer
response is replaced. The preexisting saved planner policy verdict is a fixture; the
producer portal validation and manager workflow are real. The frontend interaction
tests exercise the answer form and existing workspace workflow; this is not a claim
of a deployed two-origin browser authentication session.

Run with `TPP_REPO_PATH` pointing to an unmodified checkout at
`TPP_PINNED_REF=3010e3e39eb0ae039a1e648f957d8e87441d8e2a`:

```sh
python3 -m pytest tests/integration/test_tpp_portal_contract.py tests/integration/test_authenticated_two_app_handoff.py -q
```

Cross-Repo Smoke invokes both real-producer test files. `red-green.txt` records the
new gate on base650d1638 (both nodes fail) and repaired source (both pass). It proves
this bounded implementation, not fleet/source-wide acceptance or a provider verdict.
