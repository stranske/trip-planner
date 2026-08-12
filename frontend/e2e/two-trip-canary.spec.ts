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
  expectedLeadScenario: string;
};

function isoDate(daysFromToday: number): string {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() + daysFromToday);
  return value.toISOString().slice(0, 10);
}

async function createTripThroughApp(page: Page, input: TripInput): Promise<string> {
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

  await expect(page).toHaveURL(/\/workspace\/trip-/);
  await expect(page.getByRole("heading", { name: input.title, exact: true }).first()).toBeVisible();
  await page.getByRole("tab", { name: "Compare", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Compare", exact: true })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  await expect(
    page.getByRole("heading", { name: input.expectedLeadScenario, exact: true }).first()
  ).toBeVisible();
  await expect(page.getByText("3 runtime scenario(s)", { exact: false })).toBeVisible();
  if (process.env.VITE_GOOGLE_MAPS_BROWSER_API_KEY?.trim()) {
    await page.getByRole("tab", { name: "Map", exact: true }).click();
    await expect(page.locator('[data-google-maps-live="true"]')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Live Google Maps", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Compare", exact: true }).click();
  }
  return page.url();
}

test("a traveler can create and inspect the two-trip canary in the real app", async ({ page }, testInfo: TestInfo) => {
  const uniqueEmail = `two-trip-canary-${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Display name", { exact: true }).fill("Two Trip Canary");
  await page.getByLabel("Email", { exact: true }).fill(uniqueEmail);
  await page.getByLabel("Password", { exact: true }).fill("canary-password-2026");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page).toHaveURL(/\/trips$/);

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
    expectedLeadScenario: "Washington DC runtime bundle",
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
    expectedLeadScenario: "Kyoto runtime bundle",
  });
  await testInfo.attach("leisure-workspace", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });

  await page.goto("/trips");
  await expect(
    page.getByRole("heading", { name: "Canary Washington DC client visit", exact: true })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Canary Kyoto cultural week", exact: true })
  ).toBeVisible();
  await testInfo.attach("two-trip-canary-summary", {
    body: Buffer.from(JSON.stringify({ businessUrl, leisureUrl }, null, 2)),
    contentType: "application/json",
  });
});
