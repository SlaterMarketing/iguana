import type { APIRoute } from "astro";

import {
  buildLocalizedSitemapEntries,
  renderSitemapXmlWithAlternates,
} from "../lib/sitemap";

export const GET: APIRoute = async () => {
  const entries = await buildLocalizedSitemapEntries();
  return new Response(renderSitemapXmlWithAlternates(entries), {
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
};
