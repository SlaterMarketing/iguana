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
