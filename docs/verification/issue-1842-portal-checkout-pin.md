# Issue 1842: pinned portal contract gate

The real portal contract now independently verifies the producer checkout when
`TPP_PINNED_REF` is supplied. A missing `TPP_REPO_PATH`, missing portal source,
non-SHA pin, non-Git directory, nested directory, or different checkout revision
fails the gate before importing TPP. Local runs with neither setting still skip
the optional producer contract, and local source checkouts without a pin remain
supported. No workflow files were changed.

The checkout regressions use real temporary Git repositories, not a substitute
portal implementation. They verify gate behavior, not authenticated receipt or
manager decision return.

## Verification on 2026-10-10

- `pytest tests/app/test_portal_handoff_flow.py tests/app/test_proposal.py
  tests/app/test_proposal_handoff_schema.py tests/integrations/test_tpp_portal_handoff.py
  tests/integration/test_saved_portal_handoff.py -q -m "not slow"`: 195 passed.
- `pytest tests/integration/test_portal_contract_checkout.py
  tests/integrations/test_tpp_portal_handoff.py -q -m "not slow"`: 125 passed,
  including 13 new checkout regressions.
- `pytest tests/integration/test_portal_contract_checkout.py
  tests/app/test_planner_fallback.py tests/app/test_planner_prompt_contract.py
  tests/integrations/test_tpp_client_interface.py -q -m "not slow"`: 33 passed.
- Direct collection of `tests/integration/test_tpp_portal_contract.py` with
  `TPP_PINNED_REF=ac3bfb9f39e7a3144cbe19fd1894d333dfe93b75` and no checkout path
  exited 2 with the required-path error. Without a pin or path it skipped as intended.
- Ruff passed for all three changed/new portal contract test files.
- `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`
  passed: 478 files would be left unchanged.
- Four existing files needed formatting with the repository-pinned Black 26.10.0:
  the two planner timing tests, the planner service, and the TPP client. Their changes
  only reflow existing expressions to satisfy the required repository-wide gate.

Sandbox checks used the temporary selector-wait workaround described in
`issue-1842-handoff-metadata.md`, plus `BLACK_NUM_WORKERS=1`. The workaround is
outside the repository and changes neither product code nor test assertions.

## Task reconciliation and outstanding scope

Reviewed recent commits through `7af399805af948362754a7d8614c497c89ace16c`.
The original browser handoff tasks and four security criteria are implemented.
The real pinned-app portal contract also passed in hosted
[Cross-Repo Smoke run 38069836670](https://github.com/stranske/trip-planner/actions/runs/38069836670).
Its log resolves the producer to `ac3bfb9f39e7a3144cbe19fd1894d333dfe93b75`
and records the portal contract as `1 passed`.

The recovery scope supersedes preparation-only completion: authenticated,
owner-bound and snapshot-correlated receipt/status and recorded manager decision
return remain open pending the accepted producer contract from
[TPP issue 1658](https://github.com/stranske/Travel-Plan-Permission/issues/1658).
The current unknown delivery/decision state remains truthful until that integration
is verified. This consumer change does not claim full acceptance or deployment.

The GitHub connector refused the PR-body update because mutations require approval
and this run's approval policy is `never`. The proposed reconciled body was saved
at `/tmp/trip-planner-1872-reconciled-body.md`; the remote checklist was not updated.
The PR was verified open and ready for review through the read-only connector.

`git add` failed because `.git` is mounted read-only and Git cannot create
`index.lock`, so the requested meaningful commit could not be created. Attempts
to add `needs-human` and post the blocker comment were also refused under the
connector approval policy. The source changes remain uncommitted; an applyable
patch is saved at `/tmp/trip-planner-1872-portal-pin.patch` for the owning automation.

Frontend tests could not start because the installed tree lacks Vitest. The local
pinned TPP checkout is absent, so this iteration cannot rerun the real portal
contract; the hosted evidence above predates this gate change. Both checks remain
required on the new revision.

## Follow-up: reject changed producer source at the pinned revision

The checkout gate now rejects staged or unstaged source changes and added modules
under `src`, even when `HEAD` still matches the requested producer pin. Unpinned
local development and unrelated untracked check artifacts remain supported.
Four new regressions failed on the prior gate; all 19 checkout cases and the
combined 137 checkout/handoff cases pass after the change, using `-m "not slow"`.
The existing focused proposal/handoff batch also passed 225 cases before this change.

Live producer discovery found receipt PR 1659 merged at
`3010e3e39eb0ae039a1e648f957d8e87441d8e2a`. The earlier producer-pending note
above is historical. Its contract requires complete portal answers and an
individually authenticated owner; this consumer currently has partial prefill
answers and its own account-session identity. Consumer identity/snapshot binding,
workspace status return, and a real two-app check at the accepted producer revision
remain incomplete. This iteration does not claim those acceptance criteria.

The reconciled PR body is saved at `/tmp/trip-planner-1872-reconciled-body.md`;
the connector rejected its update because approval is required and this run's
approval policy is `never`. Updating the hosted producer pin requires the owning
high-privilege lane because workflow files are protected in this run.

The repository-wide Black check passed (478 files unchanged), as did changed-file
Ruff and whitespace checks. Staging failed because `.git` is read-only, so no
commit was created. The scoped patch is saved at
`/tmp/trip-planner-1872-source-pin.patch`. The connector also rejected the
`needs-human` label and blocker comment under the same approval restriction.
The PR was verified open and ready for review at `bf78a971`.
