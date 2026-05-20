/**
 * Bilingual route map — paths are **without** locale prefix; {@link localizePath} adds `/en` or `/es`.
 */
export const routeMap = {
  en: {
    home: "/",
    events: "/events/",
    eventDetail: "/events/:slug/",
    eventTickets: "/events/:slug/tickets/",
    locations: "/locations/",
    cityDetail: "/locations/:city/",
    comedians: "/comedians/",
    comedianDetail: "/comedians/:slug/",
    store: "/store/",
    productDetail: "/store/:slug/",
    contact: "/contact/",
    about: "/about/",
    workWithUs: "/work-with-us/",
    performWithUs: "/perform-with-us/",
    hotelsAndResorts: "/hotels-and-resorts/",
    privacyPolicy: "/legal/privacy-policy/",
    termsAndConditions: "/legal/terms-and-conditions/",
  },
  es: {
    home: "/",
    events: "/eventos/",
    eventDetail: "/eventos/:slug/",
    eventTickets: "/eventos/:slug/boletos/",
    locations: "/sedes/",
    cityDetail: "/sedes/:city/",
    comedians: "/comediantes/",
    comedianDetail: "/comediantes/:slug/",
    store: "/tienda/",
    productDetail: "/tienda/:slug/",
    contact: "/contacto/",
    about: "/nosotros/",
    workWithUs: "/trabaja-con-nosotros/",
    performWithUs: "/actua-con-nosotros/",
    hotelsAndResorts: "/hoteles-y-resorts/",
    privacyPolicy: "/legal/politica-de-privacidad/",
    termsAndConditions: "/legal/terminos-y-condiciones/",
  },
} as const;

export type RouteKey = keyof (typeof routeMap)["en"];
export type Locale = "en" | "es";

/** Replace :param placeholders in a route template. */
function interpolate(template: string, params?: Record<string, string>): string {
  if (!params) return template;
  return template.replace(/:([^/]+)/g, (_, key) => params[key] ?? `:${key}`);
}

const LOCALE_PREFIX: Record<Locale, string> = { en: "/en", es: "/es" };

/** Prefix locale segment for public URLs (`/en/events/`, `/es/eventos/`). */
export function localizePath(
  locale: Locale,
  key: RouteKey,
  params?: Record<string, string>
): string {
  const template = routeMap[locale][key];
  const path = interpolate(template, params);
  const prefix = LOCALE_PREFIX[locale];
  if (path === "/" || path === "") return `${prefix}/`;
  return `${prefix}${path}`.replace(/\/+/g, "/");
}

/** Strip the locale prefix (e.g. "/en/events/" → "/events/") */
function stripLocalePrefix(pathname: string): string {
  return pathname.replace(/^\/(en|es)\b/, "");
}

/** Reverse-lookup: given a locale and an actual pathname, find the route key. */
export function resolveRouteKey(locale: Locale, pathname: string): RouteKey | null {
  const withoutPrefix = stripLocalePrefix(pathname);
  const normalized = withoutPrefix.replace(/\/$/, "") || "/";
  const entries = Object.entries(routeMap[locale]) as [RouteKey, string][];

  for (const [key, template] of entries) {
    const pattern = template.replace(/:([^/]+)/g, "[^/]+");
    const regex = new RegExp(`^${pattern.replace(/\//g, "\\/")}$`);
    if (regex.test(normalized)) return key;
  }
  return null;
}

/** Given current locale + pathname, return the equivalent path in the other locale. */
export function getAlternatePath(locale: Locale, pathname: string): string | null {
  const key = resolveRouteKey(locale, pathname);
  if (!key) return null;
  const other: Locale = locale === "en" ? "es" : "en";

  const currentTemplate = routeMap[locale][key];
  const params: Record<string, string> = {};
  const withoutPrefix = stripLocalePrefix(pathname);
  const currentParts = currentTemplate.split("/");
  const pathParts = withoutPrefix.split("/");

  for (let i = 0; i < currentParts.length; i++) {
    if (currentParts[i].startsWith(":")) {
      const paramName = currentParts[i].slice(1);
      params[paramName] = pathParts[i] ?? "";
    }
  }

  return localizePath(other, key, params);
}
