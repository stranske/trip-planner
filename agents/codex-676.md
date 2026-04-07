# Issue #676 Workloop Bootstrap

This branch advances issue `#676` (`[Agent] [Epic] Planner workspace vertical slice`) by giving the parent epic a concrete in-repo contract instead of leaving it as a GitHub-only checklist.

## Scope For This PR Iteration

- Add an epic plan that defines the dependency order and ownership boundaries for child issues `#687`, `#688`, and `#689`.
- Align the implementation plan and repo doc index so the planner-workspace epic is visible as an explicit delivery track.
- Keep this PR parent-epic scoped rather than implementing child trip-entry, workspace, or persistence code already tracked under the child issues.

## Implementation Targets

1. Epic contract surface
- Document the workspace-slice boundary, runtime and persistence dependencies, and acceptance mapping.
- Make the child issue dependency chain explicit.

2. Planning alignment
- Add the epic to the repo doc index.
- Replace the stale frontend-layer anchor with the current runtime-backed workspace lane.

3. Follow-up safety
- Reuse the existing frontend and planner docs as references instead of forking them.
- Leave a clean handoff for future runs to continue the child workspace lanes independently.

## Validation Targets

- Review `docs/planner-workspace-vertical-slice-epic.md` for issue-to-child alignment.
- Review `docs/implementation-plan.md` for delivery-order consistency.
- Review `README.md` for doc index visibility.

## Notes

- This iteration intentionally advances the parent epic through planning and boundary-setting only.
- Child issue implementation and any prior frontend-app-shell design docs remain on their own issue lanes and references.
