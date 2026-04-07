# Issue #678 Workloop Bootstrap

This branch advances issue `#678` (`[Agent] [Epic] Budget and business policy execution surfaces`) by giving the parent epic a concrete in-repo contract instead of leaving it as a GitHub-only checklist.

## Scope For This PR Iteration

- Add an epic plan that defines the dependency order and ownership boundaries for child issues `#694`, `#695`, `#696`, and `#697`.
- Align the implementation plan and repo doc index so the budget and business-policy execution epic is visible as an explicit delivery track.
- Keep this PR parent-epic scoped rather than implementing child budget or policy workflow code already tracked under the child issues.

## Implementation Targets

1. Epic contract surface
- Document the budget and business-policy workflow boundary, upstream runtime dependencies, and acceptance mapping.
- Make the child issue dependency chain explicit.

2. Planning alignment
- Add the epic to the repo doc index.
- Replace the stale lower-level policy-execution anchor with the current runtime-backed business workflow lane.

3. Follow-up safety
- Reuse the existing persistence, planner, and policy docs as references instead of forking them.
- Leave a clean handoff for future runs to continue the child budget and policy workflow lanes independently.

## Validation Targets

- Review `docs/budget-business-policy-execution-epic.md` for issue-to-child alignment.
- Review `docs/implementation-plan.md` for delivery-order consistency.
- Review `README.md` for doc index visibility.

## Notes

- This iteration intentionally advances the parent epic through planning and boundary-setting only.
- Child issue implementation and the earlier lower-level policy integration docs remain on their own issue lanes and references.
