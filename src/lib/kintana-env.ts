import { createKintanaClient } from "@kintana/sdk";

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

export function hasKintanaCredentials(runtime?: RuntimeEnv) {
  return getKintanaEnv(runtime).hasCredentials;
}

/**
 * Kintana client with optional workspace secret — use from server contexts only (pages/middleware/endpoints).
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
