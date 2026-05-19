/**
 * Filename candidates (Business → Files, link visibility). Match ignores extension/case — see normalizeStem in ../lib/kintana-files.
 */

export type SiteBrandOverrideKeys =
  | "faviconUrl"
  | "heroLogoUrl"
  | "brandMomentImage"
  | "clubPhotoImage"
  | "heroVideoUrl";

export type SiteBrandOverrides = Partial<Record<SiteBrandOverrideKeys, string>>;

/** First matching file name wins (per key). Upload with these stems or aliases. */
export const SITE_BRAND_FILE_ALIASES: { key: SiteBrandOverrideKeys; candidates: readonly string[] }[] = [
  { key: "faviconUrl", candidates: ["site-favicon"] },
  { key: "heroLogoUrl", candidates: ["site-hero-logo", "site-logo-header"] },
  { key: "brandMomentImage", candidates: ["site-brand-moment", "brand-moment"] },
  { key: "clubPhotoImage", candidates: ["site-club-photo", "club-photo"] },
  { key: "heroVideoUrl", candidates: ["site-hero-video", "hero-video"] },
] as const;
