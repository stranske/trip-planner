import "@testing-library/jest-dom/vitest";

type TestProcess = {
  env: Record<string, string | undefined>;
};

// Keep frontend tests off UTC so date-only regressions reproduce in CI.
const testProcess = (globalThis as typeof globalThis & { process?: TestProcess }).process;
if (testProcess) {
  testProcess.env.TZ = "America/Los_Angeles";
}

Object.assign(globalThis, {
  Request,
  Response,
  Headers,
  AbortController,
  AbortSignal,
});
