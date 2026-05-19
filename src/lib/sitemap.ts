import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { createKintanaClient } from "@kintana/sdk";
import { groupVenuesByCity } from "@kintana/sdk/locations";

import { getCityBlurb } from "../content/city-blurbs";
import { getKintanaEnv } from "./kintana-env";
import { mapLegacyPath } from "./legacy-paths";
import { slugify } from "./slug";

export type SitemapEntry = {
  path: string;
  priority: number;
  lastmod?: string;
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

    const priority = Number.parseFloat(chunk.match(/<priority>([^<]+)<\/priority>/)?.[1] ?? "0.5");
    const lastmod = chunk.match(/<lastmod>([^<]+)<\/lastmod>/)?.[1]?.trim();

    entries.push({
      path: mapped,
      priority: Number.isFinite(priority) ? priority : 0.5,
      lastmod,
    });
  }

  return entries;
}

function addCorePages(map: Map<string, SitemapEntry>) {
  const core: Array<{ path: string; priority: number }> = [
    { path: "/", priority: 1 },
    { path: "/events/", priority: 0.8 },
    { path: "/locations/", priority: 0.8 },
    { path: "/comedians/", priority: 0.8 },
    { path: "/store/", priority: 0.8 },
    { path: "/contact/", priority: 0.8 },
    { path: "/about/", priority: 0.8 },
    { path: "/work-with-us/", priority: 0.8 },
    { path: "/perform-with-us/", priority: 0.85 },
    { path: "/legal/privacy-policy/", priority: 0.8 },
    { path: "/legal/terms-and-conditions/", priority: 0.8 },
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
      upsert(map, { path: `/events/${key}/`, priority: 0.64, lastmod: now });
    }
  } catch {
    /* build continues with legacy + static URLs */
  }

  try {
    const artists = await client.listArtists({ limit: 200 });
    for (const artist of artists) {
      const key = artist.slug?.trim();
      if (!key) continue;
      upsert(map, { path: `/comedians/${key}/`, priority: 0.64, lastmod: now });
    }
  } catch {
    /* noop */
  }

  try {
    const venues = await client.listVenues({ limit: 200 });
    const cities = groupVenuesByCity(venues);
    for (const city of cities) {
      const slug = slugify(city.name);
      if (!slug || !getCityBlurb(slug)) continue;
      upsert(map, { path: `/locations/${slug}/`, priority: 0.64, lastmod: now });
    }
  } catch {
    /* noop */
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

export function renderSitemapXml(entries: SitemapEntry[], origin = siteOrigin()): string {
  const urls = entries
    .map((entry) => {
      const loc = `${origin}${entry.path === "/" ? "/" : entry.path}`;
      const lastmod = entry.lastmod ? `\n    <lastmod>${entry.lastmod}</lastmod>` : "";
      return `  <url>\n    <loc>${escapeXml(loc)}</loc>${lastmod}\n    <priority>${entry.priority.toFixed(2)}</priority>\n  </url>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`;
}

function escapeXml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
