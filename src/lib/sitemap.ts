import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { createKintanaClient } from "@kintana/sdk";
import { groupVenuesByCity } from "@kintana/sdk/locations";

import { getCityBlurb } from "../content/city-blurbs";
import { getKintanaEnv } from "./kintana-env";
import { mapLegacyPath } from "./legacy-paths";
import { slugify } from "./slug";
import { localizePath, resolveRouteKey, type RouteKey } from "../i18n/routes";
import type { Locale } from "../i18n/locale";

export type SitemapEntry = {
  path: string;
  priority: number;
  lastmod?: string;
};

export type LocalizedSitemapEntry = {
  path: string;
  priority: number;
  lastmod?: string;
  alternates: Array<{ locale: string; path: string }>;
};

const DEFAULT_SITE = "https://iguanacomedy.com";

export function siteOrigin(): string {
  const raw =
    import.meta.env.PUBLIC_SITE_URL?.trim() ||
    import.meta.env.SITE?.trim() ||
    DEFAULT_SITE;
  return raw.replace(/\/$/, "");
}

function normalizePath(path: string): string {
  let p = path.trim();
  if (!p.startsWith("/")) p = `/${p}`;
  if (p.length > 1 && !p.endsWith("/")) p = `${p}/`;
  return p;
}

function upsert(map: Map<string, SitemapEntry>, entry: SitemapEntry) {
  const path = normalizePath(entry.path);
  const existing = map.get(path);
  if (!existing || entry.priority > existing.priority) {
    map.set(path, { ...entry, path });
  }
}

function upsertLocalized(
  map: Map<string, LocalizedSitemapEntry>,
  entry: LocalizedSitemapEntry
) {
  const path = normalizePath(entry.path);
  const existing = map.get(path);
  if (!existing || entry.priority > existing.priority) {
    map.set(path, { ...entry, path });
  }
}

function prefixLocale(locale: Locale, path: string): string {
  if (path === "/") return `/${locale}/`;
  return `/${locale}${path}`;
}

function parseLegacySitemapFile(): SitemapEntry[] {
  const filePath = resolve(process.cwd(), "sitemap.xml");
  let xml: string;
  try {
    xml = readFileSync(filePath, "utf8");
  } catch {
    return [];
  }

  const entries: SitemapEntry[] = [];
  for (const block of xml.matchAll(/<url>([\s\S]*?)<\/url>/g)) {
    const chunk = block[1];
    const loc = chunk.match(/<loc>([^<]+)<\/loc>/)?.[1]?.trim();
    if (!loc) continue;

    let pathname: string;
    try {
      pathname = new URL(loc).pathname;
    } catch {
      continue;
    }

    const mapped = mapLegacyPath(pathname);
    if (!mapped) continue;

    const priority = Number.parseFloat(
      chunk.match(/<priority>([^<]+)<\/priority>/)?.[1] ?? "0.5"
    );
    const lastmod = chunk.match(/<lastmod>([^<]+)<\/lastmod>/)?.[1]?.trim();

    entries.push({
      path: mapped,
      priority: Number.isFinite(priority) ? priority : 0.5,
      lastmod,
    });
  }

  return entries;
}

function addCoreLocalizedPages(map: Map<string, LocalizedSitemapEntry>) {
  const core: Array<{
    key: RouteKey;
    priority: number;
    params?: Record<string, string>;
  }> = [
    { key: "home", priority: 1 },
    { key: "events", priority: 0.8 },
    { key: "locations", priority: 0.8 },
    { key: "comedians", priority: 0.8 },
    { key: "store", priority: 0.8 },
    { key: "contact", priority: 0.8 },
    { key: "about", priority: 0.8 },
    { key: "workWithUs", priority: 0.8 },
    { key: "performWithUs", priority: 0.85 },
    { key: "hotelsAndResorts", priority: 0.85 },
    { key: "privacyPolicy", priority: 0.8 },
    { key: "termsAndConditions", priority: 0.8 },
  ];

  const now = new Date().toISOString();
  for (const page of core) {
    const enPath = localizePath("en", page.key, page.params);
    const esPath = localizePath("es", page.key, page.params);
    const alternates = [
      { locale: "en", path: enPath },
      { locale: "es", path: esPath },
    ];

    upsertLocalized(map, {
      path: enPath,
      priority: page.priority,
      lastmod: now,
      alternates,
    });
    upsertLocalized(map, {
      path: esPath,
      priority: page.priority,
      lastmod: now,
      alternates,
    });
  }
}

async function addKintanaLocalizedPages(
  map: Map<string, LocalizedSitemapEntry>
) {
  const { apiKey, baseUrl, hasCredentials } = getKintanaEnv();
  if (!hasCredentials) return;

  const now = new Date().toISOString();
  const client = createKintanaClient({ apiKey, baseUrl });

  try {
    const events = await client.listEvents({ limit: 200 });
    for (const evt of events) {
      const key = evt.slug?.trim() || evt.id?.trim();
      if (!key) continue;
      const enPath = localizePath("en", "eventDetail", { slug: key });
      const esPath = localizePath("es", "eventDetail", { slug: key });
      const alternates = [
        { locale: "en", path: enPath },
        { locale: "es", path: esPath },
      ];
      upsertLocalized(map, {
        path: enPath,
        priority: 0.64,
        lastmod: now,
        alternates,
      });
      upsertLocalized(map, {
        path: esPath,
        priority: 0.64,
        lastmod: now,
        alternates,
      });
    }
  } catch {
    /* build continues with legacy + static URLs */
  }

  try {
    const artists = await client.listArtists({ limit: 200 });
    for (const artist of artists) {
      const key = artist.slug?.trim();
      if (!key) continue;
      const enPath = localizePath("en", "comedianDetail", { slug: key });
      const esPath = localizePath("es", "comedianDetail", { slug: key });
      const alternates = [
        { locale: "en", path: enPath },
        { locale: "es", path: esPath },
      ];
      upsertLocalized(map, {
        path: enPath,
        priority: 0.64,
        lastmod: now,
        alternates,
      });
      upsertLocalized(map, {
        path: esPath,
        priority: 0.64,
        lastmod: now,
        alternates,
      });
    }
  } catch {
    /* noop */
  }

  try {
    const venues = await client.listVenues();
    const cities = groupVenuesByCity(venues);
    for (const city of cities) {
      const slug = slugify(city.city ?? "");
      if (!slug || !getCityBlurb("en", slug)) continue;
      const enPath = localizePath("en", "cityDetail", { city: slug });
      const esPath = localizePath("es", "cityDetail", { city: slug });
      const alternates = [
        { locale: "en", path: enPath },
        { locale: "es", path: esPath },
      ];
      upsertLocalized(map, {
        path: enPath,
        priority: 0.64,
        lastmod: now,
        alternates,
      });
      upsertLocalized(map, {
        path: esPath,
        priority: 0.64,
        lastmod: now,
        alternates,
      });
    }
  } catch {
    /* noop */
  }
}

function addLegacyLocalizedPages(map: Map<string, LocalizedSitemapEntry>) {
  for (const entry of parseLegacySitemapFile()) {
    const enPath = prefixLocale("en", entry.path);
    const key = resolveRouteKey("en", entry.path);
    if (key) {
      const esPath = localizePath("es", key);
      const alternates = [
        { locale: "en", path: enPath },
        { locale: "es", path: esPath },
      ];
      upsertLocalized(map, {
        path: enPath,
        priority: entry.priority,
        lastmod: entry.lastmod,
        alternates,
      });
      upsertLocalized(map, {
        path: esPath,
        priority: entry.priority,
        lastmod: entry.lastmod,
        alternates,
      });
    } else {
      upsertLocalized(map, {
        path: enPath,
        priority: entry.priority,
        lastmod: entry.lastmod,
        alternates: [{ locale: "en", path: enPath }],
      });
    }
  }
}

export function legacyEventSlugs(): string[] {
  return [
    ...new Set(
      parseLegacySitemapFile()
        .map((e) => e.path)
        .filter((p) => p.startsWith("/events/"))
        .map((p) => p.replace(/^\/events\/|\/$/g, ""))
        .filter(Boolean)
    ),
  ];
}

/** @deprecated Use legacyEventSlugs */
export const legacyShowSlugs = legacyEventSlugs;

export function legacyComedianSlugs(): string[] {
  return [
    ...new Set(
      parseLegacySitemapFile()
        .map((e) => e.path)
        .filter((p) => p.startsWith("/comedians/"))
        .map((p) => p.replace(/^\/comedians\/|\/$/g, ""))
        .filter(Boolean)
    ),
  ];
}

export function legacyCitySlugs(): string[] {
  return [
    ...new Set(
      parseLegacySitemapFile()
        .map((e) => e.path)
        .filter((p) => p.startsWith("/locations/"))
        .map((p) => p.replace(/^\/locations\/|\/$/g, ""))
        .filter(Boolean)
    ),
  ];
}

export function legacyVenueSlugs(): string[] {
  return [
    ...new Set(
      parseLegacySitemapFile()
        .map((e) => e.path)
        .filter((p) => p.startsWith("/venues/"))
        .map((p) => p.replace(/^\/venues\/|\/$/g, ""))
        .filter(Boolean)
    ),
  ];
}

export async function buildSitemapEntries(): Promise<SitemapEntry[]> {
  const map = new Map<string, SitemapEntry>();

  for (const entry of parseLegacySitemapFile()) {
    upsert(map, entry);
  }

  addCorePages(map);
  await addKintanaPages(map);

  return [...map.values()].sort((a, b) => a.path.localeCompare(b.path));
}

function addCorePages(map: Map<string, SitemapEntry>) {
  const core: Array<{ path: string; priority: number }> = [
    { path: "/en/", priority: 1 },
    { path: "/en/events/", priority: 0.8 },
    { path: "/en/locations/", priority: 0.8 },
    { path: "/en/comedians/", priority: 0.8 },
    { path: "/en/store/", priority: 0.8 },
    { path: "/en/contact/", priority: 0.8 },
    { path: "/en/about/", priority: 0.8 },
    { path: "/en/work-with-us/", priority: 0.8 },
    { path: "/en/perform-with-us/", priority: 0.85 },
    { path: "/en/hotels-and-resorts/", priority: 0.85 },
    { path: "/en/legal/privacy-policy/", priority: 0.8 },
    { path: "/en/legal/terms-and-conditions/", priority: 0.8 },
  ];

  const now = new Date().toISOString();
  for (const page of core) {
    upsert(map, { path: page.path, priority: page.priority, lastmod: now });
  }
}

async function addKintanaPages(map: Map<string, SitemapEntry>) {
  const { apiKey, baseUrl, hasCredentials } = getKintanaEnv();
  if (!hasCredentials) return;

  const now = new Date().toISOString();
  const client = createKintanaClient({ apiKey, baseUrl });

  try {
    const events = await client.listEvents({ limit: 200 });
    for (const evt of events) {
      const key = evt.slug?.trim() || evt.id?.trim();
      if (!key) continue;
      upsert(map, { path: `/en/events/${key}/`, priority: 0.64, lastmod: now });
    }
  } catch {
    /* build continues with legacy + static URLs */
  }

  try {
    const artists = await client.listArtists({ limit: 200 });
    for (const artist of artists) {
      const key = artist.slug?.trim();
      if (!key) continue;
      upsert(map, { path: `/en/comedians/${key}/`, priority: 0.64, lastmod: now });
    }
  } catch {
    /* noop */
  }

  try {
    const venues = await client.listVenues();
    const cities = groupVenuesByCity(venues);
    for (const city of cities) {
      const slug = slugify(city.city ?? "");
      if (!slug || !getCityBlurb("en", slug)) continue;
      upsert(map, { path: `/en/locations/${slug}/`, priority: 0.64, lastmod: now });
    }
  } catch {
    /* noop */
  }
}

export async function buildLocalizedSitemapEntries(): Promise<
  LocalizedSitemapEntry[]
> {
  const map = new Map<string, LocalizedSitemapEntry>();

  addLegacyLocalizedPages(map);
  addCoreLocalizedPages(map);
  await addKintanaLocalizedPages(map);

  return [...map.values()].sort((a, b) => a.path.localeCompare(b.path));
}

export function renderSitemapXml(
  entries: SitemapEntry[],
  origin = siteOrigin()
): string {
  const urls = entries
    .map((entry) => {
      const loc = `${origin}${entry.path === "/" ? "/" : entry.path}`;
      const lastmod = entry.lastmod
        ? `\n    <lastmod>${escapeXml(entry.lastmod)}</lastmod>`
        : "";
      return `  <url>\n    <loc>${escapeXml(loc)}</loc>${lastmod}\n    <priority>${entry.priority.toFixed(2)}</priority>\n  </url>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`;
}

export function renderSitemapXmlWithAlternates(
  entries: LocalizedSitemapEntry[],
  origin = siteOrigin()
): string {
  const urls = entries
    .map((entry) => {
      const loc = `${origin}${entry.path === "/" ? "/" : entry.path}`;
      const lastmod = entry.lastmod
        ? `\n    <lastmod>${escapeXml(entry.lastmod)}</lastmod>`
        : "";
      const alternates = entry.alternates
        .map(
          (alt) =>
            `    <xhtml:link rel="alternate" hreflang="${alt.locale}" href="${escapeXml(`${origin}${alt.path === "/" ? "/" : alt.path}`)}" />`
        )
        .join("\n");
      return `  <url>\n    <loc>${escapeXml(loc)}</loc>${lastmod}\n${alternates}\n    <priority>${entry.priority.toFixed(2)}</priority>\n  </url>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${urls}
</urlset>
`;
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
