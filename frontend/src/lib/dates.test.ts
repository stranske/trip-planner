import { afterEach, describe, expect, it } from "vitest";

import { formatCalendarDate, formatInstantDate } from "./dates";

// Vitest runs in Node; the frontend tsconfig carries no Node types, so reach the env this way.
const env = (globalThis as unknown as { process: { env: Record<string, string | undefined> } }).process.env;

const originalTz = env.TZ;

afterEach(() => {
  if (originalTz === undefined) {
    delete env.TZ;
  } else {
    env.TZ = originalTz;
  }
});

describe("dates", () => {
  it("keeps a calendar date on its day in a timezone west of UTC", () => {
    env.TZ = "America/Los_Angeles";
    // new Date("2026-10-05") is UTC midnight, which is October 4 in Los Angeles.
    expect(formatCalendarDate("2026-10-05")).toBe("October 5, 2026");
  });

  it("shows an instant as the reader's local day", () => {
    env.TZ = "America/New_York";
    expect(formatInstantDate("2026-09-23T01:30:00+00:00")).toBe("September 22, 2026");
    env.TZ = "Asia/Tokyo";
    expect(formatInstantDate("2026-09-22T20:00:00+00:00")).toBe("September 23, 2026");
  });

  it("says a date is absent rather than printing a blank or an invalid date", () => {
    expect(formatCalendarDate(null)).toBe("Not set");
    expect(formatInstantDate("")).toBe("Not recorded");
    expect(formatInstantDate("not a date")).toBe("Not recorded");
  });
});
