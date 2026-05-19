import type { APIRoute } from "astro";

import { buildSitemapEntries, renderSitemapXml } from "../lib/sitemap";

export const prerender = true;

export const GET: APIRoute = async () => {
  const entries = await buildSitemapEntries();
  return new Response(renderSitemapXml(entries), {
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
};
