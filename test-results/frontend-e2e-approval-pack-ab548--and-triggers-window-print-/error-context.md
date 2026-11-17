# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: frontend/e2e/approval-packet-journey.spec.ts >> policy (check -> native submit -> approval packet print (real frontend/backend + local HTTP TPP stub verifies packet renders trip title, fare, verdict, and triggers window.print)
- Location: frontend/e2e/approval-packet-journey.spec.ts:54:1

# Error details

```
Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
Call log:
  - navigating to "/signup", waiting until "load"

```

# Test source

```ts
  1  | /**
  2  |  * Policy-to-approval-packet browser canary (simulated TPP transport).
  3  |  *
  4  |  * Covered: signup, business trip creation with origin, entered prices, native policy
  5  |  * submission through the live backend + local HTTP TPP stub, approval packet rendering,
  6  |  * and print/export.
  7  |  */
  8  | import { expect, test, type Page } from "@playwright/test";
  9  | 
  10 | const TRIP_TITLE = "Canary Denver client briefing";
  11 | const TRIP_ORIGIN = "Chicago";
  12 | const TRIP_DESTINATION = "Denver";
  13 | const FARE_AMOUNT = "486";
  14 | const LOWEST_FARE = "486";
  15 | 
  16 | function isoDate(daysFromToday: number): string {
  17 |   const value = new Date();
  18 |   value.setUTCDate(value.getUTCDate() + daysFromToday);
  19 |   return value.toISOString().slice(0, 10);
  20 | }
  21 | 
  22 | async function signUp(page: Page): Promise<void> {
  23 |   const uniqueEmail = `approval-packet-canary-${Date.now()}@example.com`;
> 24 |   await page.goto("/signup");
     |              ^ Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
  25 |   await page.getByLabel("Display name", { exact: true }).fill("Approval Packet Canary");
  26 |   await page.getByLabel("Email", { exact: true }).fill(uniqueEmail);
  27 |   await page.getByLabel("Password", { exact: true }).fill("canary-password-2026");
  28 |   await page.getByRole("button", { name: "Create account", exact: true }).click();
  29 |   await expect(page).toHaveURL(/\/trips$/);
  30 | }
  31 | 
  32 | async function createBusinessTrip(page: Page): Promise<void> {
  33 |   await page.goto("/trips/new");
  34 |   await page.getByRole("radio", { name: "Business trip" }).check();
  35 |   await page.getByLabel("Trip name", { exact: true }).fill(TRIP_TITLE);
  36 |   await page
  37 |     .getByLabel("Business purpose", { exact: true })
  38 |     .fill("Two-day client briefing with one travel day on each side.");
  39 |   await page.getByLabel("Travelling from", { exact: true }).fill(TRIP_ORIGIN);
  40 |   await page.getByLabel("Destinations", { exact: true }).fill(TRIP_DESTINATION);
  41 |   await page.getByLabel("First day of travel", { exact: true }).fill(isoDate(45));
  42 |   await page.getByLabel("Last day of travel", { exact: true }).fill(isoDate(47));
  43 |   await page.getByLabel("Trip length (days)", { exact: true }).fill("3");
  44 |   await page.locator('select[name="travelerKind"]').selectOption("solo");
  45 |   await page.getByLabel("Number of travellers", { exact: true }).fill("1");
  46 |   await page
  47 |     .getByLabel("Anything the planner should know", { exact: true })
  48 |     .fill("Economy airfare and central lodging with manager review.");
  49 |   await page.getByRole("button", { name: "Create trip", exact: true }).click();
  50 |   await expect(page).toHaveURL(/\/workspace\/trip-/);
  51 |   await expect(page.getByRole("heading", { name: TRIP_TITLE, exact: true }).first()).toBeVisible();
  52 | }
  53 | 
  54 | test("policy (check -> native submit -> approval packet print (real frontend/backend + local HTTP TPP stub verifies packet renders trip title, fare, verdict, and triggers window.print)", async ({
  55 |   page,
  56 | }) => {
  57 |   await signUp(page);
  58 |   await createBusinessTrip(page);
  59 | 
  60 |   await page.getByRole("tab", { name: "Budget", exact: true }).click();
  61 |   await page.getByLabel("Flights and ground travel", { exact: true }).fill(FARE_AMOUNT);
  62 |   await page.getByLabel("Lowest fare you found for the same journey", { exact: true }).fill(LOWEST_FARE);
  63 |   await page.getByRole("button", { name: "Save Flights and ground travel", exact: true }).click();
  64 |   await expect(page.getByText(/\$486\b/)).toBeVisible();
  65 | 
  66 |   await page.getByRole("tab", { name: "Policy", exact: true }).click();
  67 |   await page.getByRole("button", { name: "Submit for approval", exact: true }).click();
  68 |   await expect(page.getByRole("heading", { name: "Policy compliant" })).toBeVisible({ timeout: 45_000 });
  69 |   await expect(page.getByText(/Policy check completed:/)).toBeVisible();
  70 | 
  71 |   const printButton = page.getByRole("button", {
  72 |     name: "Open approval packet from Policy tab",
  73 |     exact: true,
  74 |   });
  75 |   await expect(printButton).toBeEnabled();
  76 |   await printButton.click();
  77 | 
  78 |   const packet = page.getByTestId("approval-packet-document");
  79 |   await expect(packet).toBeVisible();
  80 |   await expect(packet.getByRole("heading", { level: 2, name: TRIP_TITLE })).toBeVisible();
  81 |   await expect(packet.getByTestId("approval-packet-journey")).toContainText(
  82 |     `${TRIP_ORIGIN} → ${TRIP_DESTINATION}`,
  83 |   );
  84 |   await expect(packet.getByTestId("approval-packet-trip-cost")).toContainText("$486");
  85 |   await expect(packet.getByTestId("approval-packet-verdict")).toContainText(
  86 |     "Passed the travel policy check",
  87 |   );
  88 | 
  89 |   await page.evaluate(() => {
  90 |     window.print = () => {
  91 |       (window as unknown as { __canaryPrintInvoked?: boolean }).__canaryPrintInvoked = true;
  92 |     };
  93 |   });
  94 |   await packet.getByRole("button", { name: "Print / Export", exact: true }).click();
  95 |   const printInvoked = await page.evaluate(
  96 |     () => (window as unknown as { __canaryPrintInvoked?: boolean }).__canaryPrintInvoked === true,
  97 |   );
  98 |   expect(printInvoked).toBe(true);
  99 | });
```