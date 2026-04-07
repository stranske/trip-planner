import "@testing-library/jest-dom/vitest";

Object.assign(globalThis, {
  Request,
  Response,
  Headers,
  AbortController,
  AbortSignal,
});
