import { useLoaderData } from "react-router-dom";

import type { TripRecord } from "../api/trips";
import { AsyncRouteContent } from "../lib/routes/AsyncRouteContent";
import { NewTripPage } from "./NewTripPage";

type LoaderData = { trip: Promise<TripRecord> };

/** Edit an existing trip's setup with the same form that created it (issue 1841). */
export function EditTripPage() {
  const { trip } = useLoaderData() as LoaderData;

  return (
    <AsyncRouteContent
      resolve={trip}
      loading={{ label: "Trip setup", title: "Loading trip setup", message: "Reading the saved trip." }}
      error={{
        label: "Trip setup",
        title: "Trip setup unavailable",
        message: "The app could not load this trip, so it cannot be edited.",
      }}
    >
      {(resolvedTrip) => <NewTripPage key={resolvedTrip.trip_id} existingTrip={resolvedTrip} />}
    </AsyncRouteContent>
  );
}
