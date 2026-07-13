/// <reference types="vite/client" />
/// <reference types="google.maps" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_GOOGLE_MAPS_BROWSER_API_KEY?: string;
  readonly VITE_GOOGLE_MAPS_EMBED_API_KEY?: string;
  readonly VITE_GOOGLE_MAPS_PROVIDER_STATE?: "ready" | "loading" | "error";
  readonly VITE_GOOGLE_MAPS_MAP_ID?: string;
  readonly VITE_TPP_PORTAL_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
