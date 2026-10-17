# Issue 1910 local product-probe evidence

Baseline: `47173b69d1c2d420d21983abd172e4b821038266`.
Runtime: repository-selected Python 3.14.3. No hosted-main artifact or provider PASS is claimed.

- Focused existing script/app tests: **49 passed**, zero failures/errors (see JUnit).
- Real offline report CLI: exit **0**, **WORKS 4, PARTIAL 2, BROKEN 0, FABRICATED 1 of 7**.
- Production mutation removes the TP3 cross-pair comparison and returns WORKS after successful HTTP responses. The named TestClient test produces **1 assertion failure / 2 cases** (constant figures incorrectly become WORKS); varying figures still pass. Byte-identical production restoration produces **2 passed / 2 cases**.
- Source SHA-256 before and after: `5d691dcb21fc0f01100cc7aef192c966651635e1b11d806bc72aceee4a40c44f`. Mutated hash and exact commands are in `mutation.json`.

Reproduce from any checkout with the repository interpreter:

```sh
python docs/verification/issue-1910-product-probe/reproduce_mutation.py /tmp/tp1910-mutation-new
python -m pytest tests/scripts/test_check_full_product_verification.py tests/app/test_full_product_verification.py -q
python scripts/check_full_product_verification.py --live-tpp off --contract-report /tmp/tp1910-product-probe.json
```

The mutation runner resolves the checkout via `__file__`, uses `sys.executable`, verifies the full pinned baseline exists, checks XML case counts and the actual FABRICATED/WORKS assertion, and restores source in `finally`.
Original captures remain outside the checkout. Published copies normalize local host and paths; `evidence-manifest.json` records raw/published hashes, while the original mapping is retained with the raw captures.

The capability-advisor consult was attempted before validation with `--json --lane opener --surface opener-lane --repository stranske/trip-planner` describing this implementation. It failed with PermissionError opening the capability registry lock (see `advisor-error.log`). No capability offers or declines were returned, so dispatch readiness is UNKNOWN, not an inferred approval; no assessor was launched.

Product limits: TPP policy/submission/evaluation observations use the explicitly enabled local fixture envelopes. TP4 is PARTIAL because the actual runtime is fallback. TP7 is PARTIAL because the observed persisted packet inputs do not prove browser print/export; there is no backend packet route. The existing Runtime CI and browser-canary job bodies are preserved. Current main CI, artifact upload/summary, weekly consumption, live TPP/provider behavior and human acceptance remain later gates.
