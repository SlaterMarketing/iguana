/// <reference path="../.astro/types.d.ts" />
/// <reference types="astro/client" />

interface ImportMetaEnv {
  readonly PUBLIC_SITE_URL?: string;
  readonly PUBLIC_KINTANA_API_KEY: string;
  readonly PUBLIC_KINTANA_BASE_URL: string;
  readonly PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID: string;
  readonly PUBLIC_KINTANA_TRACKER_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
