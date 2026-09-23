/**
 * Dates as a traveller and an approver read them, formatted one way everywhere.
 *
 * Two kinds of value reach the screen and they must not be confused:
 * - calendar dates ("2026-10-12"), which name a day and must never shift with the viewer's
 *   timezone; and
 * - instants ("2026-09-23T01:30:00+00:00"), which are shown as the viewer's local day.
 *
 * The approval packet used to print the prepared date in local time and entry dates as the
 * first ten characters of a UTC timestamp, so on a US evening one page said both
 * "September 22" and "2026-09-23".
 */

const LONG_DATE: Intl.DateTimeFormatOptions = { year: "numeric", month: "long", day: "numeric" };

/** "2026-10-12" → "October 12, 2026", read as that calendar day in any timezone. */
export function formatCalendarDate(value: string | null | undefined, fallback = "Not set"): string {
  if (!value) {
    return fallback;
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (!match) {
    return value;
  }
  const [, year, month, day] = match;
  return new Date(Number(year), Number(month) - 1, Number(day)).toLocaleDateString("en-US", LONG_DATE);
}

/** An instant (ISO timestamp or Date) as the viewer's local calendar day. */
export function formatInstantDate(value: string | Date | null | undefined, fallback = "Not recorded"): string {
  if (value == null || value === "") {
    return fallback;
  }
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? fallback : date.toLocaleDateString("en-US", LONG_DATE);
}
