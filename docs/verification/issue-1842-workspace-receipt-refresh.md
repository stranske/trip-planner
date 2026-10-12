# Issue 1842: owner-bound workspace receipt refresh

This round implements the receipt-read and workspace-display portion of the
authorized status-return scope. It does not complete authenticated preparation
or resolve review r4174712854. No parent task checkbox is marked complete.

The accepted producer implementation is PR1659, merged at
`3010e3e39eb0ae039a1e648f957d8e87441d8e2a`, for producer issue1658. The contract
at that exact revision is `docs/contracts/portal-receipt-v1.md` (blob
`cfcc2048e45489d75b62e5260944b0b1d612bdcd`). It provides machine-readable
owner-authenticated observations. The older assertion that TPP has no receipt
endpoint is therefore obsolete; unknown state remains appropriate until a
validated observation exists.

`POST /api/workspace/{trip_id}/proposal/handoff/status` takes an empty JSON body.
It resolves local session ownership before any producer lookup and accepts no
destination, receipt, owner or correlation fields from the browser. The trusted
server integration supplies `OwnerPortalReceiptClient` through `create_app`.
Its explicit identity resolver must map the local account to an authenticated
TPP traveler in the validated provider/issuer/audience namespace. There is no
shared-service fallback or automatic subject minting. Credentials remain in
memory and are excluded from identity representations and durable metadata.

The reader uses the validated fixed HTTPS origin, refuses redirects, bounds
response size, and distinguishes failed, absent, unauthorized and stale reads
from successful receipt evidence. Refresh requires the producer binding and
owner namespace retained by authenticated preparation. It validates the exact
binding and observation history before saving request/review state or a manager
decision. Public payloads contain status metadata, observation/decision times
and the existing source hash; producer correlation and identity stay private.

Recorded decisions survive failed reads as historical evidence. Changed trip
facts are reported stale on reload and refresh. A delayed read cannot overwrite
a newer preparation or observation. An unchanged policy-result refresh retains
the receipt; the legacy browser preparation route cannot reset an owner-bound
decision. The Policy tab displays actual decisions and observation time, labels
unavailable/stale evidence as historical, and provides a refresh action.

Validation on 2026-10-12:

- 672 focused backend regressions passed with `-m "not slow"` across receipt
  validation, new reader/workspace services, saved handoffs and proposal routes.
- The final workspace suite passed 24 cases, including three subsequently added
  prepared/submitted/pending-review cases. The reader suite passed 15 cases.
- New source and tests pass Ruff; changed runtime modules pass Mypy. Existing
  proposal files retain their pre-existing Ruff findings.
- The required repository-wide Black check at line length100 passed (485 files).
  TypeScript syntax checking and `git diff --check` passed.
- Black and ASGI regression checks used the previously documented temporary
  selector-wait cap under `/tmp/trip-planner-receipt-checks`; repository assertions
  and runtime code were unchanged by that runner adjustment.

Frontend behavior and type checking remain unverified: offline npm lacks
`xmlchars-2.2.0.tgz`, online installation fails DNS resolution, and Vitest is
unavailable. The eight new component cases have not run.

Required follow-up remains substantive: implement traveler-completed answer
collection and authenticated producer preparation, retain its owner/binding,
obtain the view-only browser review capability, and provision the trusted
traveler identity bridge. The default app has no configured bridge, and the
legacy browser handoff establishes no receipt binding; both deliberately return
unavailable/unknown. Preserve submitted snapshot history when preparing a new
version. Run the two-app contract against the accepted checkout and qualify
frontend behavior and hosted exact-head checks. Updating the protected
cross-repo workflow's producer pin requires the authorized workflow owner;
this agent has not edited workflow files.
