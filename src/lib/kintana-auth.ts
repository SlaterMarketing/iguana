import { createKintanaClient } from "@kintana/sdk";
import { localizePath, type Locale } from "../i18n/routes";
import { getKintanaEnv } from "./kintana-env";

const STORAGE_KEY = "kintana_access_token";
const DEFAULT_SITE = "https://iguanacomedy.com";

export function readStoredAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(STORAGE_KEY)?.trim() || null;
  } catch {
    return null;
  }
}

export function writeStoredAccessToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) localStorage.setItem(STORAGE_KEY, token);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function createAuthenticatedClientFromEnv() {
  const token = readStoredAccessToken();
  const { apiKey, baseUrl } = getKintanaEnv();
  return createKintanaClient({
    apiKey: apiKey!,
    baseUrl: baseUrl!,
    accessToken: token ?? undefined,
  });
}

export function membershipPaths(locale: Locale) {
  return {
    membership: localizePath(locale, "membership"),
    account: localizePath(locale, "account"),
    accountSignIn: localizePath(locale, "accountSignIn"),
    accountVerify: localizePath(locale, "accountVerify"),
    accountTickets: localizePath(locale, "accountTickets"),
    accountProfile: localizePath(locale, "accountProfile"),
    accountRegister: localizePath(locale, "accountRegister"),
    events: localizePath(locale, "events"),
  };
}

function checkoutSiteOrigin(): string {
  if (typeof window !== "undefined") {
    return window.location.origin.replace(/\/$/, "");
  }
  const { siteUrl } = getKintanaEnv();
  return (siteUrl ?? DEFAULT_SITE).replace(/\/$/, "");
}

export function accountVerifyRedirectUrl(locale: Locale): string {
  return `${checkoutSiteOrigin()}${membershipPaths(locale).accountVerify}`;
}

export function accountReturnUrl(locale: Locale): string {
  return `${checkoutSiteOrigin()}${membershipPaths(locale).account}`;
}

export function membershipSuccessUrl(locale: Locale): string {
  return `${checkoutSiteOrigin()}${membershipPaths(locale).account}?membership=1`;
}

export function membershipCancelUrl(locale: Locale): string {
  return `${checkoutSiteOrigin()}${membershipPaths(locale).membership}`;
}

export function signInUrlWithNext(locale: Locale, nextPath: string): string {
  const path = nextPath.startsWith("/") ? nextPath : `/${nextPath}`;
  const signIn = membershipPaths(locale).accountSignIn;
  return `${signIn}?next=${encodeURIComponent(path)}`;
}

export function numberLocale(locale: Locale): string {
  return locale === "es" ? "es-MX" : "en-US";
}
