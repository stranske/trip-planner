import { describe, expect, it } from "vitest";

import { policyCheckStatusMessage } from "./policyCheckStatus";

describe("policyCheckStatusMessage", () => {
  it.each(["approval-ready", "completed-with-follow-up"] as const)(
    "reports a completed policy check for %s without claiming manager submission",
    (state) => {
      expect(policyCheckStatusMessage({ state, summary: "Saved verdict." })).toBe(
        "Policy check completed: Saved verdict."
      );
    }
  );

  it.each(["pending", "deferred", "running"] as const)(
    "keeps %s checks pending until a verdict arrives",
    (state) => {
      expect(policyCheckStatusMessage({ state, summary: "Awaiting a verdict." })).toBe(
        "Policy check pending: Awaiting a verdict."
      );
    }
  );

  it("reports a transport failure without claiming completion or submission", () => {
    expect(policyCheckStatusMessage({ state: "failed", summary: "Gateway unavailable." })).toBe(
      "Policy check failed: Gateway unavailable."
    );
  });
});
