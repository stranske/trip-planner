/**
 * Policy-to-approval-packet browser canary (simulated TPP transport).
 *
 * Covered: signup, business trip creation with origin, entered prices, native policy
 * submission through the live backend + local HTTP TPP stub, approval packet rendering,
 * and print/export.
 */
import { expect, test, type Page } from "@playwright/test";

const TRIP_TITLE = "Canary Denver client briefing";
const TRIP_ORIGIN = "Chicago";
const TRIP_DESTINATION = "Denver";
const FARE_AMOUNT = "486";
const LOWEST_FARE = "486";

function isoDate(daysFromToday: number): string {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() + daysFromToday);
  return value.toISOString().slice(0, 10);
}

async function signUp(page: Page): Promise<void> {
  const uniqueEmail = `approval-packet-canary-${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Display name", { exact: true }).fill("Approval Packet Canary");
  await page.getByLabel("Email", { exact: true }).fill(uniqueEmail);
  await page.getByLabel("Password", { exact: true }).fill("canary-password-2026");
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page).toHaveURL(/\/trips$/);
}

async function createBusinessTrip(page: Page): Promise<void> {
  await page.goto("/trips/new");
  await page.getByRole("radio", { name: "Business trip" }).check();
  await page.getByLabel("Trip name", { exact: true }).fill(TRIP_TITLE);
  await page
    .getByLabel("Business purpose", { exact: true })
    .fill("Two-day client briefing with one travel day on each side.");
  await page.getByLabel("Travelling from", { exact: true }).fill(TRIP_ORIGIN);
  await page.getByLabel("Destinations", { exact: true }).fill(TRIP_DESTINATION);
  await page.getByLabel("First day of travel", { exact: true }).fill(isoDate(45));
  await page.getByLabel("Last day of travel", { exact: true }).fill(isoDate(47));
  await page.getByLabel("Trip length (days)", { exact: true }).fill("3");
  await page.locator('select[name="travelerKind"]').selectOption("solo");
  await page.getByLabel("Number of travellers", { exact: true }).fill("1");
  await page
    .getByLabel("Anything the planner should know", { exact: true })
    .fill("Economy airfare and central lodging with manager review.");
  await page.getByRole("button", { name: "Create trip", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace\/trip-/);
  await expect(page.getByRole("heading", { name: TRIP_TITLE, exact: true }).first()).toBeVisible();
}

test("policy (check -> native submit -> approval packet print (real frontend/backend + local HTTP TPP stub verifies packet renders trip title, fare, verdict, and triggers window.print)", async ({
  page,
}) => {
  await signUp(page);
  await createBusinessTrip(page);

  await page.getByRole("tab", { name: "Budget", exact: true }).click();
  await page.getByLabel("Flights and ground travel", { exact: true }).fill(FARE_AMOUNT);
  await page.getByLabel("Lowest fare you found for the same journey", { exact: true }).fill(LOWEST_FARE);
  await page.getByRole("button", { name: "Save Flights and ground travel", exact: true }).click();
  await expect(page.getByText(/\$486\b/)).toBeVisible();

  await page.getByRole("tab", { name: "Policy", exact: true }).click();
  await page.getByRole("button", { name: "Submit for approval", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Policy compliant" })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText(/Policy check completed:/)).toBeVisible();

  const printButton = page.getByRole("button", {
    name: "Open approval packet from Policy tab",
    exact: true,
  });
  await expect(printButton).toBeEnabled();
  await printButton.click();

  const packet = page.getByTestId("approval-packet-document");
  await expect(packet).toBeVisible();
  await expect(packet.getByRole("heading", { level: 2, name: TRIP_TITLE })).toBeVisible();
  await expect(packet.getByTestId("approval-packet-journey")).toContainText(
    `${TRIP_ORIGIN} → ${TRIP_DESTINATION}`,
  );
  await expect(packet.getByTestId("approval-packet-trip-cost")).toContainText("$486");
  await expect(packet.getByTestId("approval-packet-verdict")).toContainText(
    "Passed the travel policy check",
  );

  await page.evaluate(() => {
    window.print = () => {
      (window as unknown as { __canaryPrintInvoked?: boolean }).__canaryPrintInvoked = true;
    };
  });
  await packet.getByRole("button", { name: "Print / Export", exact: true }).click();
  const printInvoked = await page.evaluate(
    () => (window as unknown as { __canaryPrintInvoked?: boolean }).__canaryPrintInvoked === true,
  );
  expect(printInvoked).toBe(true);
});