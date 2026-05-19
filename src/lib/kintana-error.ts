import { KintanaApiError } from "@kintana/sdk";

/** HTTP status from a failed SDK call (`401` = publish key rejected; `403` often mean scope). */
export function kintanaHttpStatus(error: unknown): number | undefined {
  return error instanceof KintanaApiError ? error.status : undefined;
}

/** Log in dev/production; avoids silent empty UI when credentials are wrong. */
export function logKintanaError(scope: string, error: unknown) {
  const detail =
    error instanceof KintanaApiError ? `HTTP ${error.status}` : error instanceof Error ? error.message.slice(0, 200) : String(error).slice(0, 120);
  console.error(`[Kintana:${scope}]`, detail);
}

/**
 * Astro runs on the server: this prints where `npm run dev` is attached, not Chrome DevTools.
 */
export function logKintanaSuccess(scope: string, count: number) {
  /** Use `.log` (not `.info`): some consoles hide INFO level when filtered. */
  if (import.meta.env.DEV) console.log(`[Kintana:${scope}] OK — ${count} row(s)`);
}
