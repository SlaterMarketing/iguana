import { createKintanaClient } from "@kintana/sdk";
import type { KintanaClient, KintanaPublicEvent } from "@kintana/sdk";
import { groupVenuesByCity } from "@kintana/sdk/locations";

import { getCityBlurb } from "../content/city-blurbs";
import { eventCitySlug, todayInCancun } from "./events";
import { getKintanaEnv } from "./kintana-env";
import { isOpenMic } from "./open-mics";
import { slugify } from "./slug";
import { localizePath, type RouteKey } from "../i18n/routes";

/**
 * One `<url>` per language. Every entry lists both languages plus `x-default` (the English URL) as alternates.
 * `lastmod` is only set from a real modification time; the public API exposes none today, so it is omitted.
 */
export type LocalizedSitemapEntry = {
  path: string;
  priority: number;
  lastmod?: string;
  alternates: Array<{ locale: string; path: string }>;
};

const DEFAULT_SITE = "https://iguanacomedy.com";

/** Playa del Carmen always has the club, so its city page is listed even with no dated shows. */
const ALWAYS_LISTED_CITY = "playa-del-carmen";

/** Weekly open mics are generated months ahead; only advertise the next few weeks of them. */
const OPEN_MIC_WINDOW_DAYS = 21;

export function siteOrigin(): string {
  const raw = import.meta.env.PUBLIC_SITE_URL?.trim() || import.meta.env.SITE?.trim() || DEFAULT_SITE;
  return raw.replace(/\/$/, "");
}

function normalizePath(path: string): string {
  let p = path.trim();
  if (!p.startsWith("/")) p = `/${p}`;
  if (p.length > 1 && !p.endsWith("/")) p = `${p}/`;
  return p;
}

/** Adds the English and Spanish URL for one route, each carrying en, es and x-default alternates. */
function addRoute(
  map: Map<string, LocalizedSitemapEntry>,
  key: RouteKey,
  priority: number,
  params?: Record<string, string>,
) {
  const enPath = normalizePath(localizePath("en", key, params));
  const esPath = normalizePath(localizePath("es", key, params));
  const alternates = [
    { locale: "en", path: enPath },
    { locale: "es", path: esPath },
    { locale: "x-default", path: enPath },
  ];
  for (const path of [enPath, esPath]) {
    const existing = map.get(path);
    if (!existing || priority > existing.priority) map.set(path, { path, priority, alternates });
  }
}

const CORE_PAGES: Array<{ key: RouteKey; priority: number }> = [
  { key: "home", priority: 1 },
  { key: "events", priority: 0.8 },
  { key: "locations", priority: 0.8 },
  { key: "comedians", priority: 0.8 },
  { key: "membership", priority: 0.8 },
  { key: "contact", priority: 0.8 },
  { key: "about", priority: 0.8 },
  { key: "workWithUs", priority: 0.8 },
  { key: "performWithUs", priority: 0.85 },
  { key: "hotelsAndResorts", priority: 0.85 },
  { key: "privacyPolicy", priority: 0.8 },
  { key: "termsAndConditions", priority: 0.8 },
];

/** `YYYY-MM-DD` plus `days`, computed on the calendar date so no timezone shifts it. */
function addDays(isoDay: string, days: number): string {
  const [y, m, d] = isoDay.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** Upcoming, not cancelled, and for open mics only within the next few weeks. */
function listableEvents(events: KintanaPublicEvent[], today: string): KintanaPublicEvent[] {
  const openMicCutoff = addDays(today, OPEN_MIC_WINDOW_DAYS);
  return events.filter((evt) => {
    if (evt.status === "past" || evt.status === "cancelled") return false;
    const day = evt.date?.slice(0, 10) ?? "";
    if (day && day < today) return false;
    if (isOpenMic(evt) && (!day || day > openMicCutoff)) return false;
    return true;
  });
}

async function addApiPages(map: Map<string, LocalizedSitemapEntry>, client: KintanaClient) {
  const today = todayInCancun();

  // Events from today onward: the unfiltered list starts at the oldest shows and would crowd out upcoming ones.
  let upcoming: KintanaPublicEvent[] = [];
  try {
    upcoming = (await client.listEvents({ limit: 200, from: today })).filter(
      (evt) => evt.status !== "past" && evt.status !== "cancelled",
    );
    for (const evt of listableEvents(upcoming, today)) {
      const slug = evt.slug?.trim() || evt.id?.trim();
      if (slug) addRoute(map, "eventDetail", 0.64, { slug });
    }
  } catch {
    /* sitemap still lists the static pages */
  }

  try {
    for (const artist of await client.listArtists({ limit: 200 })) {
      const slug = artist.slug?.trim();
      if (slug) addRoute(map, "comedianDetail", 0.64, { slug });
    }
  } catch {
    /* noop */
  }

  try {
    const citiesWithShows = new Set(upcoming.map(eventCitySlug));
    for (const city of groupVenuesByCity(await client.listVenues())) {
      const slug = slugify(city.city);
      if (slug === "unknown" || !getCityBlurb("en", slug)) continue;
      if (slug !== ALWAYS_LISTED_CITY && !citiesWithShows.has(slug)) continue;
      addRoute(map, "cityDetail", 0.64, { city: slug });
    }
  } catch {
    /* noop */
  }

  try {
    const products = await client.listStoreProducts({ limit: 100 });
    const slugs = products.map((product) => product.slug?.trim()).filter((slug): slug is string => Boolean(slug));
    if (slugs.length) addRoute(map, "store", 0.8);
    for (const slug of slugs) addRoute(map, "productDetail", 0.5, { slug });
  } catch {
    /* noop */
  }
}

export async function buildLocalizedSitemapEntries(): Promise<LocalizedSitemapEntry[]> {
  const map = new Map<string, LocalizedSitemapEntry>();
  for (const page of CORE_PAGES) addRoute(map, page.key, page.priority);

  const { apiKey, baseUrl, hasCredentials } = getKintanaEnv();
  if (hasCredentials) await addApiPages(map, createKintanaClient({ apiKey, baseUrl }));

  return [...map.values()].sort((a, b) => a.path.localeCompare(b.path));
}

/**
 * Venue slugs from the retired Framer site. Only `src/pages/en/venues/[...slug].astro` uses this, and it redirects
 * every venue URL to the locations page either way, so a fixed list is enough.
 */
export function legacyVenueSlugs(): string[] {
  return [
    "aqui-ahora",
    "bipolar",
    "los-chilacos-de-playa",
    "live-music-hall",
    "batey",
    "harvest-comedy",
    "ophelia-speakeasy",
    "shhhh",
    "civil-sin-project",
    "casa-iguana",
    "beplaya",
    "buzos",
  ];
}

export function renderSitemapXmlWithAlternates(entries: LocalizedSitemapEntry[], origin = siteOrigin()): string {
  const abs = (path: string) => escapeXml(`${origin}${path}`);
  const urls = entries
    .map((entry) => {
      const lastmod = entry.lastmod ? `\n    <lastmod>${escapeXml(entry.lastmod)}</lastmod>` : "";
      const alternates = entry.alternates
        .map((alt) => `    <xhtml:link rel="alternate" hreflang="${alt.locale}" href="${abs(alt.path)}" />`)
        .join("\n");
      return `  <url>\n    <loc>${abs(entry.path)}</loc>${lastmod}\n${alternates}\n    <priority>${entry.priority.toFixed(2)}</priority>\n  </url>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${urls}
</urlset>
`;
}

function escapeXml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
