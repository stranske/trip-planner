import { describe, expect, it } from "vitest";

import { googleFlightsSearchUrl } from "./fareSearch";

describe("googleFlightsSearchUrl", () => {
  it("builds the round-trip search that was checked against Google Flights", () => {
    expect(
      googleFlightsSearchUrl({
        origin: "Chicago",
        primary_regions: ["New York, NY"],
        start_date: "2026-11-10",
        end_date: "2026-11-11",
      })
    ).toBe(
      "https://www.google.com/travel/flights?q=Flights%20to%20New%20York%2C%20NY%20from%20Chicago%20on%202026-11-10%20through%202026-11-11&hl=en&curr=USD"
    );
  });

  it("offers no fare search for a trip that cannot be submitted without a return date", () => {
    const url = googleFlightsSearchUrl({
      origin: "Seattle",
      primary_regions: ["Boston"],
      start_date: "2026-11-10",
      end_date: null,
    });
    expect(url).toBeNull();
  });

  it("offers no search it cannot build", () => {
    expect(
      googleFlightsSearchUrl({ origin: "", primary_regions: ["Boston"], start_date: "2026-11-10", end_date: null })
    ).toBeNull();
    expect(
      googleFlightsSearchUrl({ origin: "Seattle", primary_regions: [], start_date: "2026-11-10", end_date: null })
    ).toBeNull();
  });
});
