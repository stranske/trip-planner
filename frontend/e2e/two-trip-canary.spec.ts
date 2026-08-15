/**
 * Required browser canary for the first-use journey.
 *
 * Covered: account signup, trip creation, workspace navigation, workspace title,
 * scenario comparison, and returning to the persisted trip list.
 * Not covered: live travel-provider calls, paid map rendering, planner-LLM output,
 * policy approval, or production deployment/authentication configuration.
 */
import { expect, test, type Page, type TestInfo } from "@playwright/test";

type TripInput = {
  title: string;
  summary: string;
  mode: "business" | "leisure";
  regions: string;
  startDate: string;
  endDate: string;
  durationDays: string;
  travelerKind: "solo" | "team";
  travelerCount: string;
  travelerNotes: string;
};

function isoDate(daysFromToday: number): string {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() + daysFromToday);
  return value.toISOString().slice(0, 10);
}

async function createTripThroughApp(page: Page, input: TripInput): Promise<string> {
  return test.step(`create trip: ${input.title}`, async () => {
    await page.goto("/trips/new");
    await page.getByLabel("Title", { exact: true }).fill(input.title);
    await page.getByLabel("Summary", { exact: true }).fill(input.summary);
    await page.locator('select[name="mode"]').selectOption(input.mode);
    await page.getByLabel("Primary regions", { exact: true }).fill(input.regions);
    await page.getByLabel("Start date", { exact: true }).fill(input.startDate);
    await page.getByLabel("End date", { exact: true }).fill(input.endDate);
    await page.getByLabel("Duration days", { exact: true }).fill(input.durationDays);
    await page.locator('select[name="travelerKind"]').selectOption(input.travelerKind);
    await page.getByLabel("Traveler count", { exact: true }).fill(input.travelerCount);
    await page.getByLabel("Traveler notes", { exact: true }).fill(input.travelerNotes);
    await page.getByRole("button", { name: "Create trip", exact: true }).click();

    await test.step(`open workspace: ${input.title}`, async () => {
      await expect(page).toHaveURL(/\/workspace\/trip-/);
      await expect(page.getByRole("heading", { name: input.title, exact: true }).first()).toBeVisible();
      await page.getByRole("tab", { name: "Compare", exact: true }).click();
      await expect(page.getByRole("tab", { name: "Compare", exact: true })).toHaveAttribute(
        "aria-selected",
        "true",
      );
    });
    return page.url();
  });
}

test("signup, trip creation, and workspace navigation work in the real app", async ({ page }, testInfo: TestInfo) => {
  await test.step("signup through the real interface", async () => {
    const uniqueEmail = `two-trip-canary-${Date.now()}@example.com`;
    await page.goto("/signup");
    await page.getByLabel("Display name", { exact: true }).fill("Two Trip Canary");
    await page.getByLabel("Email", { exact: true }).fill(uniqueEmail);
    await page.getByLabel("Password", { exact: true }).fill("canary-password-2026");
    await page.getByRole("button", { name: "Create account", exact: true }).click();
    await expect(page).toHaveURL(/\/trips$/);
  });

  const businessUrl = await createTripThroughApp(page, {
    title: "Canary Washington DC client visit",
    summary: "Three travelers attending a two-day client meeting with an arrival buffer.",
    mode: "business",
    regions: "Washington DC",
    startDate: isoDate(75),
    endDate: isoDate(77),
    durationDays: "3",
    travelerKind: "team",
    travelerCount: "3",
    travelerNotes: "Economy travel, central lodging, explicit budget, and manager review.",
  });
  await testInfo.attach("business-workspace", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });

  const leisureUrl = await createTripThroughApp(page, {
    title: "Canary Kyoto cultural week",
    summary: "Seven days focused on Kyoto culture, food, and low-transfer neighborhood exploration.",
    mode: "leisure",
    regions: "Kyoto, Osaka",
    startDate: isoDate(90),
    endDate: isoDate(96),
    durationDays: "7",
    travelerKind: "solo",
    travelerCount: "1",
    travelerNotes: "Moderate budget, cultural sites, local food, and simple transfers via Osaka.",
  });
  await testInfo.attach("leisure-workspace", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });

  await test.step("reopen both trips from the saved-trips interface", async () => {
    await page.goto("/trips");
    for (const title of [
      "Canary Washington DC client visit",
      "Canary Kyoto cultural week",
    ]) {
      const tripCard = page.getByRole("heading", { name: title, exact: true }).locator("..");
      await tripCard.getByRole("link", { name: "Open planner", exact: true }).click();
      await expect(page).toHaveURL(/\/workspace\/trip-/);
      await expect(page.getByRole("heading", { name: title, exact: true }).first()).toBeVisible();
      await page.goto("/trips");
    }
  });
  await testInfo.attach("two-trip-canary-summary", {
    body: Buffer.from(JSON.stringify({ businessUrl, leisureUrl }, null, 2)),
    contentType: "application/json",
  });
});
