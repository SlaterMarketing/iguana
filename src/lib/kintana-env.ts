import { createKintanaClient } from "@kintana/sdk";

import type { Locale } from "../i18n/locale";

type RuntimeEnv = Record<string, string | undefined>;

function readEnv(key: string, runtime?: RuntimeEnv): string {
  const fromRuntime = runtime?.[key]?.trim();
  if (fromRuntime) return fromRuntime;

  const fromProcess =
    typeof process !== "undefined" ? process.env[key]?.trim() : undefined;
  if (fromProcess) return fromProcess;

  const fromImport = import.meta.env[key as keyof ImportMetaEnv];
  return typeof fromImport === "string" ? fromImport.trim() : "";
}

/** Server/runtime env (Cloudflare Pages, local `.env`) with build-time fallback. */
export function getKintanaEnv(runtime?: RuntimeEnv) {
  const apiKey = readEnv("PUBLIC_KINTANA_API_KEY", runtime);
  const baseUrl = readEnv("PUBLIC_KINTANA_BASE_URL", runtime);
  const trackerToken = readEnv("PUBLIC_KINTANA_TRACKER_TOKEN", runtime);
  const siteUrl = readEnv("PUBLIC_SITE_URL", runtime);
  const secretApiKey = readEnv("KINTANA_SECRET_API_KEY", runtime);

  return {
    apiKey,
    baseUrl,
    trackerToken,
    siteUrl,
    /** Server-only (`kpa_secret_…`). Omit from browsers and islands. */
    secretApiKey: secretApiKey || undefined,
    hasCredentials: Boolean(apiKey && baseUrl),
    hasWorkspaceSecret: Boolean(secretApiKey),
  };
}

/**
 * Client that asks the API for one language: event names, descriptions and posters, and artist bios, come back in
 * it. Without this every page got the English row, so /es/ showed English event names and English poster artwork.
 */
export function createLocalizedKintanaClient(locale: Locale) {
  const { apiKey, baseUrl } = getKintanaEnv();
  return createKintanaClient({ apiKey, baseUrl, fetch: withLocale(locale) });
}

function withLocale(locale: Locale): typeof fetch {
  return (input, init) => {
    const href = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(href);
    if (!url.searchParams.has("locale")) url.searchParams.set("locale", locale);
    return typeof input === "string" || input instanceof URL
      ? fetch(url, init)
      : fetch(new Request(url, input), init);
  };
}

export function hasKintanaCredentials(runtime?: RuntimeEnv) {
  return getKintanaEnv(runtime).hasCredentials;
}

/**
 * Kintana client with optional workspace secret. Use from server contexts only (pages/middleware/endpoints).
 * Passes `secretApiKey` when `KINTANA_SECRET_API_KEY` is set (embed-form workspace writes, CRM field helpers).
 */
export function createKintanaClientFromEnv() {
  const { apiKey, baseUrl, secretApiKey } = getKintanaEnv();
  return createKintanaClient({
    apiKey,
    baseUrl,
    ...(secretApiKey ? { secretApiKey } : {}),
  });
}
