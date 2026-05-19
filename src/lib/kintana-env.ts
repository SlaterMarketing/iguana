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

  return {
    apiKey,
    baseUrl,
    formId,
    trackerToken,
    siteUrl,
    hasCredentials: Boolean(apiKey && baseUrl),
  };
}
