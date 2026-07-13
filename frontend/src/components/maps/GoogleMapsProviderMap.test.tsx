import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GoogleMapsProviderMap } from "./GoogleMapsProviderMap";
import { loadGoogleMapsLibraries } from "./googleMapsLoader";
import type { MapMarker, RouteStop } from "./mapSurface";

vi.mock("./googleMapsLoader", () => ({
  loadGoogleMapsLibraries: vi.fn(),
}));

const routeStops: RouteStop[] = [
  { id: "stop-1", sourceId: "kyoto", label: "Kyoto", description: "Start", sourceRefs: [], x: 10, y: 20 },
  { id: "stop-2", sourceId: "uji", label: "Uji", description: "End", sourceRefs: [], x: 80, y: 70 },
];
const markers: MapMarker[] = routeStops.map((stop) => ({
  id: `${stop.id}-marker`,
  sourceId: stop.sourceId,
  kind: "stop",
  label: stop.label,
  summary: stop.description,
  detail: stop.description,
  x: stop.x,
  y: stop.y,
  emphasized: false,
  focusCues: [],
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("GoogleMapsProviderMap", () => {
  it("loads Google libraries, geocodes trip stops, and renders live provider state", async () => {
    class LatLng {
      constructor(public lat: number, public lng: number) {}
    }
    class LatLngBounds {
      extend = vi.fn();
    }
    const geocode = vi
      .fn()
      .mockResolvedValueOnce({ results: [{ geometry: { location: new LatLng(35.01, 135.76) } }] })
      .mockResolvedValueOnce({ results: [{ geometry: { location: new LatLng(34.89, 135.8) } }] });
    const fitBounds = vi.fn();
    class ProviderMap {
      fitBounds = fitBounds;
    }
    const setMap = vi.fn();
    class Polyline {
      setMap = setMap;
    }
    class AdvancedMarkerElement {
      map: unknown;
      addEventListener = vi.fn();
      constructor(options: { map: unknown }) {
        this.map = options.map;
      }
    }
    vi.mocked(loadGoogleMapsLibraries).mockResolvedValue({
      core: { LatLngBounds } as unknown as google.maps.CoreLibrary,
      geocoding: { Geocoder: class { geocode = geocode; } } as unknown as google.maps.GeocodingLibrary,
      maps: { Map: ProviderMap, Polyline } as unknown as google.maps.MapsLibrary,
      marker: { AdvancedMarkerElement } as unknown as google.maps.MarkerLibrary,
    });

    render(
      <GoogleMapsProviderMap
        apiKey="test-key"
        title="Kyoto route"
        markers={markers}
        routeStops={routeStops}
        destinationAnchors={["Kyoto", "Uji"]}
        onSelectMarker={vi.fn()}
        fallback={<div>fallback sketch</div>}
      />
    );

    await waitFor(() => expect(screen.getByText("Live Google Maps")).toBeInTheDocument());
    const liveMap = screen.getByRole("application", { name: "Live Google map for Kyoto route" });
    expect(liveMap).toBeInTheDocument();
    expect(liveMap.closest("[data-google-maps-live]")).toHaveAttribute(
      "data-google-maps-live",
      "true"
    );
    expect(geocode).toHaveBeenCalledTimes(2);
    expect(fitBounds).toHaveBeenCalled();
  });

  it("shows the route sketch when the SDK fails", async () => {
    vi.mocked(loadGoogleMapsLibraries).mockRejectedValue(new Error("SDK blocked"));

    render(
      <GoogleMapsProviderMap
        apiKey="test-key"
        title="Kyoto route"
        markers={markers}
        routeStops={routeStops}
        destinationAnchors={["Kyoto"]}
        onSelectMarker={vi.fn()}
        fallback={<div>fallback sketch</div>}
      />
    );

    await waitFor(() => expect(screen.getByText(/SDK blocked/)).toBeInTheDocument());
    expect(screen.getByText("fallback sketch")).toBeInTheDocument();
  });

  it("uses supplied trip coordinates without requiring Google geocoding", async () => {
    const geocode = vi.fn().mockRejectedValue(new Error("Geocoding API disabled"));
    const fitBounds = vi.fn();
    class LatLngBounds {
      extend = vi.fn();
    }
    class ProviderMap {
      fitBounds = fitBounds;
    }
    class Polyline {
      setMap = vi.fn();
    }
    class AdvancedMarkerElement {
      map: unknown;
      addEventListener = vi.fn();
      constructor(options: { map: unknown }) {
        this.map = options.map;
      }
    }
    vi.mocked(loadGoogleMapsLibraries).mockResolvedValue({
      core: { LatLngBounds } as unknown as google.maps.CoreLibrary,
      geocoding: { Geocoder: class { geocode = geocode; } } as unknown as google.maps.GeocodingLibrary,
      maps: { Map: ProviderMap, Polyline } as unknown as google.maps.MapsLibrary,
      marker: { AdvancedMarkerElement } as unknown as google.maps.MarkerLibrary,
    });
    const locatedMarkers = markers.map((marker, index) => ({
      ...marker,
      latitude: 38.85 + index * 0.05,
      longitude: -77.04,
    }));

    render(
      <GoogleMapsProviderMap
        apiKey="test-key"
        title="Washington route"
        markers={locatedMarkers}
        routeStops={routeStops}
        destinationAnchors={["Washington DC"]}
        onSelectMarker={vi.fn()}
        fallback={<div>fallback sketch</div>}
      />
    );

    await waitFor(() => expect(screen.getByText("Live Google Maps")).toBeInTheDocument());
    expect(geocode).not.toHaveBeenCalled();
    expect(fitBounds).toHaveBeenCalled();
  });
});
