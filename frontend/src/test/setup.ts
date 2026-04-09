import "@testing-library/jest-dom/vitest";

// Keep frontend tests off UTC so date-only regressions reproduce in CI.
process.env.TZ = "America/Los_Angeles";

Object.assign(globalThis, {
  Request,
  Response,
  Headers,
  AbortController,
  AbortSignal,
});
