/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GOOGLE_MAPS_BROWSER_API_KEY?: string;
  readonly VITE_GOOGLE_MAPS_EMBED_API_KEY?: string;
  readonly VITE_GOOGLE_MAPS_PROVIDER_STATE?: "ready" | "loading" | "error";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
