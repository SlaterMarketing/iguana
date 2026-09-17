import { kintanaHttpStatus } from "./kintana-error";

/**
 * HTTP status for a detail page (event, comedian, product) whose API lookup failed or never ran.
 *
 * Unknown slugs used to render a "not found" shell with 200, so search engines indexed them. The API saying the
 * thing does not exist is a real 404; anything else (API down, no credentials) is a 503, so an outage never gets
 * real pages dropped from search as "not found".
 */
export function detailPageStatus(error: unknown, hasCredentials: boolean): number {
  if (!hasCredentials) return 503;
  return kintanaHttpStatus(error) === 404 ? 404 : 503;
}
