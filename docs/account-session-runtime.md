# Account And Session Runtime

Issue `#683` adds the first runtime-backed account access layer for the Trip Planner application.

## What This Covers

- small-business-sized email/password accounts
- cookie-backed application sessions
- backend auth routes for sign up, sign in, sign out, and session restore
- frontend login/signup entry screens and protected workspace loading

## Deliberate Limits

- no SSO, SCIM, SAML, or enterprise identity management
- no role matrix beyond basic authenticated app access
- no password reset or recovery workflow yet
- no external IdP dependency before the persistence foundation is stable

## Runtime Assumptions

- The first persistence baseline uses `SQLite` plus `SQLAlchemy`.
- Schema changes are applied through Alembic migrations at app startup.
- Session cookies are `HttpOnly`, `SameSite=Lax`, and sized for local/runtime development.
- Session records store a hash of the cookie token, not the raw token itself.
- Protected app routes should call the backend session check before hydrating workspace data.

## Handoff To Later Issues

- Issue `#684` can attach persisted trip ownership directly to authenticated users.
- Issues `#685` and `#686` can build on the same session-aware runtime bootstrap instead of inventing their own entry contract.
