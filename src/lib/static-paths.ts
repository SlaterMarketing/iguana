/** Merge API slugs with legacy sitemap slugs for prerendered routes. */
export function mergeSlugs(apiSlugs: string[], legacySlugs: string[]): string[] {
  return [...new Set([...apiSlugs, ...legacySlugs].map((s) => s.trim()).filter(Boolean))];
}
