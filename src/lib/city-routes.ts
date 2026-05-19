/** Spotlight city picker and coast links. */
export function cityLocationPath(slug: string): string {
  const trimmed = slug.trim();
  if (!trimmed.length) return "/";
  return `/locations/${trimmed}/`;
}
