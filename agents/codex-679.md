# Issue #679 Workloop Bootstrap

This branch advances issue `#679` (`[Agent] [Epic] Maps, timeline, and comparison application surfaces`) by giving the parent epic a concrete in-repo contract instead of leaving it as a GitHub-only checklist.

## Scope For This PR Iteration

- Add an epic plan that defines the dependency order and ownership boundaries for child issues `#698`, `#699`, and `#700`.
- Align the implementation plan and repo doc index so the visualization epic is visible as an explicit delivery track.
- Keep this PR parent-epic scoped rather than implementing child timeline, map, or comparison code already tracked under the child issues.

## Implementation Targets

1. Epic contract surface
- Document the visualization boundary, upstream runtime and persistence dependencies, and acceptance mapping.
- Make the child issue dependency chain explicit.

2. Planning alignment
- Add the epic to the repo doc index.
- Add the active visualization lane to the implementation plan alongside the existing runtime, persistence, workspace, and policy tracks.

3. Follow-up safety
- Reuse the existing frontend, workspace, and planner docs as references instead of forking them.
- Leave a clean handoff for future runs to continue the child visualization lanes independently.

## Validation Targets

- Review `docs/maps-timeline-comparison-epic.md` for issue-to-child alignment.
- Review `docs/implementation-plan.md` for delivery-order consistency.
- Review `README.md` for doc index visibility.

## Notes

- This iteration intentionally advances the parent epic through planning and boundary-setting only.
- Child issue implementation and the broader frontend design docs remain on their own issue lanes and references.
