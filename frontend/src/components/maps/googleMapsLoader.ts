import { importLibrary, setOptions } from "@googlemaps/js-api-loader";

export type GoogleMapsLibraries = {
  core: google.maps.CoreLibrary;
  geocoding: google.maps.GeocodingLibrary;
  maps: google.maps.MapsLibrary;
  marker: google.maps.MarkerLibrary;
};

let configuredKey: string | null = null;
let librariesPromise: Promise<GoogleMapsLibraries> | null = null;

export function loadGoogleMapsLibraries(apiKey: string): Promise<GoogleMapsLibraries> {
  const normalizedKey = apiKey.trim();
  if (normalizedKey === "") {
    return Promise.reject(new Error("Google Maps requires a browser API key."));
  }
  if (configuredKey != null && configuredKey !== normalizedKey) {
    return Promise.reject(
      new Error("Google Maps was already configured with a different browser API key.")
    );
  }
  if (librariesPromise == null) {
    configuredKey = normalizedKey;
    setOptions({
      key: normalizedKey,
      v: "weekly",
      authReferrerPolicy: "origin",
    });
    librariesPromise = Promise.all([
      importLibrary("core"),
      importLibrary("geocoding"),
      importLibrary("maps"),
      importLibrary("marker"),
    ]).then(([core, geocoding, maps, marker]) => ({ core, geocoding, maps, marker }));
  }
  return librariesPromise;
}

export function resetGoogleMapsLoaderForTests() {
  configuredKey = null;
  librariesPromise = null;
}
