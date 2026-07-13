import { defineConfig } from "@playwright/test";

const artifactDirectory =
  process.env.TRIP_PLANNER_CANARY_ARTIFACT_DIR ?? "/tmp/trip-planner-two-trip-canary-artifacts";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  outputDir: artifactDirectory,
  reporter: [["list"]],
  use: {
    baseURL: process.env.TRIP_PLANNER_CANARY_BASE_URL ?? "http://127.0.0.1:5173",
    channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL ?? "chrome",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
