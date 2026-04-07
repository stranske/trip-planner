# Issue #675 Workloop Bootstrap

This branch advances issue `#675` (`[Agent] [Epic] Accounts, persistence, and workflow state`) by giving the parent epic a concrete in-repo contract instead of leaving it as a GitHub-only checklist.

## Scope For This PR Iteration

- Add an epic plan that defines the dependency order and ownership boundaries for child issues `#683`, `#684`, `#685`, and `#686`.
- Align the implementation plan and repo doc index so the persistence epic is visible as an explicit delivery track.
- Keep this PR parent-epic scoped rather than implementing child persistence code already tracked under the child issues.

## Implementation Targets

1. Epic contract surface
- Document the persistence epic boundary, runtime dependency, and acceptance mapping.
- Make the child issue dependency chain explicit.

2. Planning alignment
- Add the epic to the repo doc index.
- Replace the stale persistence phase anchor with the current runtime-backed epic lane.

3. Follow-up safety
- Reuse the earlier persistence design docs as references instead of forking them.
- Leave a clean handoff for future runs to continue the child persistence lanes independently.

## Validation Targets

- Review `docs/accounts-persistence-workflow-state-epic.md` for issue-to-child alignment.
- Review `docs/implementation-plan.md` for delivery-order consistency.
- Review `README.md` for doc index visibility.

## Notes

- This iteration intentionally advances the parent epic through planning and boundary-setting only.
- Child issue implementation and completion debt remain on their own issue lanes and PRs.
