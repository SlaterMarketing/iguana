import type { AstroGlobal } from "astro";
import type { Locale } from "./ui";
import { getAlternatePath } from "./routes";

export type { Locale } from "./ui";

export const locales: readonly Locale[] = ["en", "es"];
export const defaultLocale: Locale = "en";

/** Extract locale from pathname (Spanish under /es/) or, if present, Astro i18n metadata. */
export function getLocale(astro: AstroGlobal): Locale {
  const path = astro.url.pathname;
  if (path === "/es" || path.startsWith("/es/")) return "es";
  const lc = astro.currentLocale;
  if (lc === "es") return "es";
  return "en";
}

/** Build a full canonical URL for the current page. */
export function getCanonicalUrl(astro: AstroGlobal): string {
  const site = astro.site?.origin ?? "https://iguanacomedy.com";
  return `${site}${astro.url.pathname}`;
}

/** Build alternate URLs for every locale variant of the current page. */
export function getAlternateUrls(
  astro: AstroGlobal
): Array<{ locale: Locale; url: string }> {
  const site = astro.site?.origin ?? "https://iguanacomedy.com";
  const currentLocale = getLocale(astro);
  const currentPath = astro.url.pathname;

  return locales.map((locale) => {
    if (locale === currentLocale) {
      return { locale, url: `${site}${currentPath}` };
    }
    const altPath = getAlternatePath(currentLocale, currentPath);
    return { locale, url: altPath ? `${site}${altPath}` : `${site}/${locale}/` };
  });
}

/** Locale-aware date formatter. */
export function formatDate(
  locale: Locale,
  date: Date | string,
  options?: Intl.DateTimeFormatOptions
): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat(locale === "es" ? "es-MX" : "en-GB", {
    year: "numeric",
    month: "long",
    day: "numeric",
    ...options,
  }).format(d);
}

/** Locale-aware time formatter. */
export function formatTime(
  locale: Locale,
  date: Date | string,
  options?: Intl.DateTimeFormatOptions
): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat(locale === "es" ? "es-MX" : "en-US", {
    hour: "numeric",
    minute: "2-digit",
    ...options,
  }).format(d);
}

/** Locale-aware currency formatter. */
export function formatCurrency(
  locale: Locale,
  amount: number,
  currency = "USD"
): string {
  return new Intl.NumberFormat(locale === "es" ? "es-MX" : "en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);
}
