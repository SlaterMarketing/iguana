/** URL slug for Riviera city names etc. */
export function slugify(text: string | null | undefined): string {
  if (!text?.trim()) return "unknown";
  return text
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}
