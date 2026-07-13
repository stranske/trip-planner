import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type { MapMarker, RouteStop } from "./mapSurface";
import { loadGoogleMapsLibraries } from "./googleMapsLoader";

type ProviderState = "loading" | "ready" | "error";

type GeocodedMarker = {
  marker: MapMarker;
  position: google.maps.LatLng | google.maps.LatLngLiteral;
};

const geocodeCache = new Map<string, google.maps.LatLng | google.maps.LatLngLiteral>();

function queryForMarker(marker: MapMarker, destinationAnchors: string[]): string {
  const regionalContext = destinationAnchors.slice(0, 2).join(", ");
  return regionalContext && !marker.label.toLowerCase().includes(regionalContext.toLowerCase())
    ? `${marker.label}, ${regionalContext}`
    : marker.label;
}

async function geocodeVisibleMarkers(
  geocoder: google.maps.Geocoder,
  markers: MapMarker[],
  destinationAnchors: string[]
): Promise<GeocodedMarker[]> {
  const visibleMarkers = markers.slice(0, 10);
  const suppliedCoordinates = visibleMarkers.flatMap((marker) =>
    marker.latitude != null && marker.longitude != null
      ? [{
        marker,
        position: { lat: marker.latitude, lng: marker.longitude },
      }]
      : []
  );
  if (suppliedCoordinates.length > 0) {
    return suppliedCoordinates;
  }

  const resolved: GeocodedMarker[] = [];
  for (const marker of visibleMarkers) {
    const query = queryForMarker(marker, destinationAnchors);
    let position = geocodeCache.get(query);
    if (position == null) {
      try {
        const response = await geocoder.geocode({ address: query });
        position = response.results[0]?.geometry.location;
      } catch {
        position = undefined;
      }
      if (position != null) {
        geocodeCache.set(query, position);
      }
    }
    if (position != null) {
      resolved.push({ marker, position });
    }
  }
  return resolved;
}

export function GoogleMapsProviderMap({
  apiKey,
  mapId,
  title,
  markers,
  routeStops,
  destinationAnchors,
  onSelectMarker,
  fallback,
}: {
  apiKey: string;
  mapId?: string;
  title: string;
  markers: MapMarker[];
  routeStops: RouteStop[];
  destinationAnchors: string[];
  onSelectMarker: (markerId: string) => void;
  fallback: ReactNode;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [providerState, setProviderState] = useState<ProviderState>("loading");
  const [providerError, setProviderError] = useState<string | null>(null);
  const markerSignature = useMemo(
    () => markers.map((marker) => `${marker.id}:${marker.label}`).join("|"),
    [markers]
  );
  const routeStopSignature = useMemo(
    () => routeStops.map((stop) => `${stop.id}:${stop.label}`).join("|"),
    [routeStops]
  );
  const destinationSignature = destinationAnchors.join("|");
  const stableMarkers = useMemo(() => markers, [markerSignature]);
  const stableRouteStops = useMemo(() => routeStops, [routeStopSignature]);
  const stableDestinationAnchors = useMemo(
    () => destinationAnchors,
    [destinationSignature]
  );

  useEffect(() => {
    let cancelled = false;
    const advancedMarkers: google.maps.marker.AdvancedMarkerElement[] = [];
    let routeLine: google.maps.Polyline | null = null;

    setProviderState("loading");
    setProviderError(null);

    async function initialize() {
      const container = containerRef.current;
      if (container == null) {
        return;
      }
      try {
        const libraries = await loadGoogleMapsLibraries(apiKey);
        if (cancelled) {
          return;
        }
        const geocoder = new libraries.geocoding.Geocoder();
        const geocoded = await geocodeVisibleMarkers(
          geocoder,
          stableMarkers,
          stableDestinationAnchors
        );
        if (cancelled) {
          return;
        }
        if (geocoded.length === 0) {
          throw new Error("Google Maps could not resolve any visible trip locations.");
        }

        const bounds = new libraries.core.LatLngBounds();
        const map = new libraries.maps.Map(container, {
          center: geocoded[0].position,
          zoom: 8,
          mapId: mapId?.trim() || "DEMO_MAP_ID",
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: true,
        });
        const positionByMarkerId = new Map(
          geocoded.map(({ marker, position }) => [marker.id, position])
        );
        for (const { marker, position } of geocoded) {
          bounds.extend(position);
          const providerMarker = new libraries.marker.AdvancedMarkerElement({
            map,
            position,
            title: marker.label,
            gmpClickable: true,
          });
          providerMarker.addEventListener("gmp-click", () => onSelectMarker(marker.id));
          advancedMarkers.push(providerMarker);
        }
        const routePath = stableRouteStops
          .map((stop) => positionByMarkerId.get(`${stop.id}-marker`))
          .filter(
            (position): position is google.maps.LatLng | google.maps.LatLngLiteral =>
              position != null
          );
        if (routePath.length > 1) {
          routeLine = new libraries.maps.Polyline({
            map,
            path: routePath,
            strokeColor: "#285d50",
            strokeOpacity: 0.9,
            strokeWeight: 4,
          });
        }
        if (geocoded.length > 1) {
          map.fitBounds(bounds, 48);
        }
        setProviderState("ready");
      } catch (error) {
        if (!cancelled) {
          setProviderState("error");
          setProviderError(
            error instanceof Error ? error.message : "Google Maps failed to initialize."
          );
        }
      }
    }

    void initialize();
    return () => {
      cancelled = true;
      for (const marker of advancedMarkers) {
        marker.map = null;
      }
      routeLine?.setMap(null);
    };
  }, [apiKey, mapId, onSelectMarker, stableDestinationAnchors, stableMarkers, stableRouteStops]);

  if (providerState === "error") {
    return (
      <div className="map-provider-runtime" data-provider-state="error">
        <p className="map-warning" role="status">
          {providerError} Showing the route sketch instead.
        </p>
        {fallback}
      </div>
    );
  }

  return (
    <div
      className="map-provider-runtime"
      data-provider-state={providerState}
      data-google-maps-live={providerState === "ready" ? "true" : "false"}
    >
      <div className="map-provider-live-status" role="status">
        {providerState === "ready" ? "Live Google Maps" : "Loading Google Maps…"}
      </div>
      <div
        ref={containerRef}
        className="map-provider-canvas map-provider-canvas-google"
        role="application"
        aria-label={`Live Google map for ${title}`}
      />
    </div>
  );
}
