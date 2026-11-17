# Reconciled PR body — #2046 (approval-packet browser canary)

Apply this checklist to the GitHub PR description when `gh pr edit` is available.
Evidence: `docs/verification/pr-2046-approval-packet-canary.md`, commits `039d13fb` / `87d7f2eb`.

## Progress

**6/6 tasks complete** (including both acceptance criteria).

### Scope

Add an isolated local HTTP TPP test double started and cleaned up by `scripts/run_two_trip_ui_canary.sh` (wired via `TPP_BASE_URL` to the real FastAPI backend) returning deterministic policy, submission, and evaluation responses. Add `frontend/e2e/approval-packet-journey.spec.ts` exercising signup, business trip creation with origin, price entry, Policy check, native Submit, opening ApprovalPacket, and asserting `window.print` invocation, and run it in CI labeled as simulated TPP transport.

### Tasks

- [x] `scripts/run_two_trip_ui_canary.sh` — launch isolated local Python HTTP TPP stub, export `TPP_BASE_URL` to backend, clean up PID on EXIT/ERR, and invoke `frontend/e2e/approval-packet-journey.spec.ts`
- [x] `frontend/e2e/approval-packet-journey.spec.ts` — drive real UI through signup → business trip → price → policy check → Submit → ApprovalPacket → `window.print` stub check
- [x] `frontend/package.json` + `.github/workflows/ci.yml` — include `approval-packet-journey.spec.ts` in canary run and label artifact output as simulated TPP transport

### Additional PR tasks

- [x] `./scripts/run_two_trip_ui_canary.sh` (ports 8806/5184/8114): **2 passed**, including the named `approval-packet-journey` test.
- [x] Deliberate break: removed `ApprovalPacket` mount in `WorkspacePage.tsx` → named test **failed** (`getByTestId('approval-packet-document')` not visible).
- [x] Revert → named test **passed** again (`2 passed` in canary).

### Acceptance criteria

- [x] Named test `frontend/e2e/approval-packet-journey.spec.ts` :: policy (check → native submit → approval packet print …) passes in the repository frontend test runner (`npm --prefix frontend run test:e2e:approval-packet-journey` or `test:e2e:canary` via `scripts/run_two_trip_ui_canary.sh`).
- [x] Deliberate break → revert recorded in PR history: `039d13fb` (mount removed → named test failed); `87d7f2eb` (mount restored → **2 passed**).