/// <reference path="../.astro/types.d.ts" />
/// <reference types="astro/client" />

type Runtime = import("@astrojs/cloudflare").Runtime<Env>;

declare namespace App {
  interface Locals extends Runtime {}
}

interface Env {
  PUBLIC_SITE_URL?: string;
  PUBLIC_KINTANA_API_KEY?: string;
  PUBLIC_KINTANA_BASE_URL?: string;
  PUBLIC_KINTANA_TRACKER_TOKEN?: string;
  KINTANA_SECRET_API_KEY?: string;
}

interface ImportMetaEnv {
  readonly PUBLIC_SITE_URL?: string;
  readonly PUBLIC_KINTANA_API_KEY: string;
  readonly PUBLIC_KINTANA_BASE_URL: string;
  readonly PUBLIC_KINTANA_TRACKER_TOKEN?: string;
  /** Server-only; load from `.env` / runtime, never expose with `PUBLIC_`. */
  readonly KINTANA_SECRET_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.xml?raw" {
  const content: string;
  export default content;
}
