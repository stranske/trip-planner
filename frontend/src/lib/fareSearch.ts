/**
 * A Google Flights search for the trip, opened by the traveller in their own browser.
 *
 * Google publishes no API for reading fares, so the planner does not fetch them. It builds
 * the search, the traveller sees the fares themselves, and pastes back the fare they chose,
 * the lowest one, and the page's link, which the packet prints as fare evidence. Verified
 * 2026-10-14: the `q=` form below opens the right round-trip search. A return date is
 * required because the proposal submission contract does not accept one-way trips.
 */

export type FareSearchTrip = {
  origin?: string | null;
  primary_regions: string[];
  start_date: string | null;
  end_date: string | null;
};

export function googleFlightsSearchUrl(trip: FareSearchTrip): string | null {
  const origin = (trip.origin ?? "").trim();
  const destination = (trip.primary_regions[0] ?? "").trim();
  if (!origin || !destination || !trip.start_date || !trip.end_date) {
    return null;
  }
  const dates = `on ${trip.start_date} through ${trip.end_date}`;
  const query = `Flights to ${destination} from ${origin} ${dates}`;
  return `https://www.google.com/travel/flights?q=${encodeURIComponent(query)}&hl=en&curr=USD`;
}
