/** Map Framer-era paths to canonical routes on this site (trailing slash). */
export function mapLegacyPath(pathname: string): string | null {
  let path = pathname.trim();
  if (!path.startsWith("/")) path = `/${path}`;
  if (path.length > 1 && !path.endsWith("/")) path = `${path}/`;

  if (path === "/venues/") return "/en/locations/";
  if (path.startsWith("/venues/")) return "/en/locations/";

  if (path === "/private-events/") return "/en/work-with-us/";
  if (path === "/hotels-and-resorts/") return "/en/hotels-and-resorts/";
  if (path === "/investors/") return "/en/work-with-us/";
  if (path === "/comedy-for-everyone/") return "/en/about/";

  return path;
}

const LEGACY_EVENT_SLUGS: Record<string, string> = {
  "st-paddys-comedy-2025": "st-paddys-day-comedy-playa-del-carmen",
  "andre-de-freitas-eurotrip-2026": "andre-de-freitas-eurotrip-playa-del-carmen",
};

const LEGACY_COMEDIAN_SLUGS: Record<string, string> = {
  "liam-slater": "liam-slater-1",
};

const LEGACY_CITIES = new Set(["cancun", "cozumel", "merida", "playa-del-carmen", "puerto-aventuras", "puerto-morelos", "tulum"]);

const LEGACY_PAGES: Record<string, string> = {
  "/about/": "/en/about/",
  "/blog/": "/en/",
  "/comedians/": "/en/comedians/",
  "/contact/": "/en/contact/",
  "/events/": "/en/events/",
  "/faqs/": "/en/about/",
  "/hotels-and-resorts/": "/en/hotels-and-resorts/",
  "/locations/": "/en/locations/",
  "/perform-with-us/": "/en/perform-with-us/",
  "/work-with-us/": "/en/work-with-us/",
  "/legal/privacy-policy/": "/en/legal/privacy-policy/",
  "/legal/terms-and-conditions/": "/en/legal/terms-and-conditions/",
};

/**
 * 301 target for a URL from the Framer-era iguanacomedy.com (no locale prefix), or null when the path is not
 * a known old URL. Old event pages mostly point at shows that are no longer published, so unknown event slugs
 * land on the calendar instead of a dead page.
 */
export function legacyRedirectTarget(pathname: string): string | null {
  if (/^\/(en|es)(\/|$)/.test(pathname) || /\.[a-z0-9]{2,5}$/i.test(pathname)) return null;
  const path = pathname.endsWith("/") ? pathname : `${pathname}/`;

  if (LEGACY_PAGES[path]) return LEGACY_PAGES[path];

  const comedian = /^\/comedians\/([^/]+)\/$/.exec(path);
  if (comedian) {
    const slug = comedian[1]!;
    if (slug === "you") return "/en/perform-with-us/";
    return `/en/comedians/${LEGACY_COMEDIAN_SLUGS[slug] ?? slug}/`;
  }

  const event = /^\/events\/([^/]+)\/$/.exec(path);
  if (event) {
    const slug = LEGACY_EVENT_SLUGS[event[1]!];
    return slug ? `/en/events/${slug}/` : "/en/events/";
  }

  const city = /^\/(?:locations|comedy-in)[/-]([^/]+)\/$/.exec(path);
  if (city && LEGACY_CITIES.has(city[1]!)) return `/en/locations/${city[1]}/`;

  return null;
}
