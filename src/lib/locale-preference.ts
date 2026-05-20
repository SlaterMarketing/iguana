import type { Locale } from "../i18n/locale";

/** Stores explicit language choice (`en` | `es`); set when the visitor uses the site language switcher. */
export const LOCALE_PREFERENCE_COOKIE = "iguana_locale";

export const LOCALE_PREFERENCE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

/**
 * Pick the first supported locale (en or es) in Accept-Language order.
 * Ignores unsupported tags until it finds en or es.
 */
export function preferredLocaleFromAcceptLanguage(header: string | null): Locale {
  if (!header?.trim()) return "en";

  for (const segment of header.split(",")) {
    const [langSpec, ...params] = segment.trim().split(";").map((s) => s.trim());
    if (!langSpec) continue;

    let q = 1;
    for (const p of params) {
      if (p.startsWith("q=")) {
        const n = parseFloat(p.slice(2));
        if (Number.isFinite(n)) q = n;
        break;
      }
    }
    if (q <= 0) continue;

    const primary = langSpec.toLowerCase().split("-")[0];
    if (primary === "es") return "es";
    if (primary === "en") return "en";
  }

  return "en";
}

/** Root `/` redirect: remembered choice wins, otherwise browser language. */
export function resolveRootLocale(args: {
  preferenceCookie: string | null | undefined;
  acceptLanguage: string | null;
}): Locale {
  const c = args.preferenceCookie?.trim();
  if (c === "en" || c === "es") return c;
  return preferredLocaleFromAcceptLanguage(args.acceptLanguage);
}
