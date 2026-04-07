# Issue #674 Workloop Bootstrap

This branch advances issue `#674` (`[Agent] [Epic] Application foundation and full-stack runtime`) by giving the parent epic a concrete in-repo contract instead of leaving it as a GitHub-only checklist.

## Scope For This PR Iteration

- Add an epic plan that defines the dependency order and ownership boundaries for child issues `#680`, `#681`, and `#682`.
- Align the implementation plan and repo doc index so the application foundation is visible as an explicit delivery track.
- Keep this PR parent-epic scoped rather than re-implementing child issue code already tracked elsewhere.

## Implementation Targets

1. Epic contract surface
- Document the app foundation epic boundary and acceptance mapping.
- Make the child issue dependency chain explicit.

2. Planning alignment
- Add the epic to the repo doc index.
- Call out the runtime foundation as a cross-cutting implementation track.

3. Follow-up safety
- Avoid duplicating the concrete runtime/bootstrap work already covered by issues `#680`, `#681`, and `#682`.
- Leave a clean handoff for future runs to continue the child lanes independently.

## Validation Targets

- Review `docs/application-foundation-epic.md` for issue-to-child alignment.
- Review `docs/implementation-plan.md` for delivery-order consistency.
- Review `README.md` for doc index visibility.

## Notes

- This iteration intentionally advances the parent epic through planning and boundary-setting only.
- Child issue implementation and completion debt remain on their own issue lanes and PRs.
