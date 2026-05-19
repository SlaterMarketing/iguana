import { createKintanaClient } from "@kintana/sdk";

/** Server/runtime env (Dokploy) with build-time fallback for local dev. */
export function getKintanaEnv() {
  const fromProcess = (key: string) =>
    typeof process !== "undefined" ? process.env[key]?.trim() : undefined;

  const apiKey = fromProcess("PUBLIC_KINTANA_API_KEY") || import.meta.env.PUBLIC_KINTANA_API_KEY?.trim() || "";
  const baseUrl = fromProcess("PUBLIC_KINTANA_BASE_URL") || import.meta.env.PUBLIC_KINTANA_BASE_URL?.trim() || "";
  const formId =
    fromProcess("PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID") ||
    import.meta.env.PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID?.trim() ||
    "";
  const trackerToken =
    fromProcess("PUBLIC_KINTANA_TRACKER_TOKEN") || import.meta.env.PUBLIC_KINTANA_TRACKER_TOKEN?.trim() || "";
  const siteUrl = fromProcess("PUBLIC_SITE_URL") || import.meta.env.PUBLIC_SITE_URL?.trim() || "";
  const secretApiKey =
    fromProcess("KINTANA_SECRET_API_KEY") || import.meta.env.KINTANA_SECRET_API_KEY?.trim() || "";

  return {
    apiKey,
    baseUrl,
    formId,
    trackerToken,
    siteUrl,
    /** Server-only (`kpa_secret_…`). Omit from browsers and islands. */
    secretApiKey: secretApiKey || undefined,
    hasCredentials: Boolean(apiKey && baseUrl),
    hasWorkspaceSecret: Boolean(secretApiKey),
  };
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
