# Issue #677 Workloop Bootstrap

This branch advances issue `#677` (`[Agent] [Epic] Runtime planning services above normalized options and objectives`) by giving the parent epic a concrete in-repo contract instead of leaving it as a GitHub-only checklist.

## Scope For This PR Iteration

- Add an epic plan that defines the dependency order and ownership boundaries for child issues `#690`, `#691`, `#692`, and `#693`.
- Align the implementation plan and repo doc index so the runtime planning-services epic is visible as an explicit delivery track.
- Keep this PR parent-epic scoped rather than implementing child inventory, feasibility, ranking, or route-comparison code already tracked under the child issues.

## Implementation Targets

1. Epic contract surface
- Document the runtime service boundary, lower-level planning dependencies, and acceptance mapping.
- Make the child issue dependency chain explicit.

2. Planning alignment
- Add the epic to the repo doc index.
- Replace the stale lower-level ranking/route anchor with the current runtime-backed services lane.

3. Follow-up safety
- Reuse the existing planning and workspace docs as references instead of forking them.
- Leave a clean handoff for future runs to continue the child runtime-service lanes independently.

## Validation Targets

- Review `docs/runtime-planning-services-epic.md` for issue-to-child alignment.
- Review `docs/implementation-plan.md` for delivery-order consistency.
- Review `README.md` for doc index visibility.

## Notes

- This iteration intentionally advances the parent epic through planning and boundary-setting only.
- Child issue implementation and the earlier lower-level planning docs remain on their own issue lanes and references.
