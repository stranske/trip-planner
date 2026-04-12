# Frontend Route Loading Foundation

Issue `#681` establishes a single frontend seam for runtime-backed routes instead of letting each screen invent its own `fetch` and state orchestration.

## Shared API Client

- `frontend/src/lib/api/client.ts` is the only default entry point for JSON runtime requests.
- The client always requests JSON, surfaces typed responses, and normalizes HTTP and payload failures into `ApiClientError`.
- Route modules such as `frontend/src/api/health.ts` and `frontend/src/api/workspace.ts` stay thin and domain-focused; they should declare payload types and call the shared client rather than owning transport logic.

## Route-Level Data Loading

- `frontend/src/lib/routes/loaders.ts` provides the shared deferred-loader helper for route data.
- Route modules should export a loader alongside the route component:
  - loader calls the shared domain fetch function
  - route component reads the loader promise from `useLoaderData`
  - `AsyncRouteContent` owns the standard loading and error cards
- This keeps health, workspace, and later trip routes on one predictable pattern.

## Expected Pattern For New Routes

1. Define the response type and domain fetch function under `frontend/src/api/`.
2. Export a route loader with `createDeferredLoader`.
3. Render the route with `AsyncRouteContent` so loading and failure treatment stay consistent.
4. Add route tests that cover success plus at least one loading or failure path through the shared client seam.

## Current Coverage

- `HealthPage`, `TripsPage`, `TripDetailPage`, and `WorkspacePage` all load through the shared route/client seam instead of owning ad hoc `fetch` wiring.
- Auth-aware route loaders gate login/signup, trip list/detail, and workspace entry through the same session bootstrap path.
- Tests cover client success/error handling, route-level loading/error treatment, and the React Router future flags already opted into by the runtime and test harnesses.
- Deferred gaps stay explicit here: live external policy transport and provider-backed maps are separate runtime layers, not hidden assumptions inside the current route loader foundation.
