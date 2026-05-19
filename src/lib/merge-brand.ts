import { site } from "../content/site";
import type { SiteBrandOverrides } from "../content/site-assets";

export type MergedSite = typeof site;

/** Merge curated Kintana file URLs → site constant (fallback unchanged). */
export function mergeBrand(overrides: SiteBrandOverrides | undefined): MergedSite {
  const o = overrides ?? {};
  return {
    ...site,
    faviconUrl: o.faviconUrl ?? site.faviconUrl,
    heroLogoUrl: o.heroLogoUrl ?? site.heroLogoUrl,
    brandMomentImage: o.brandMomentImage ?? site.brandMomentImage,
    clubPhotoImage: o.clubPhotoImage ?? site.clubPhotoImage,
    heroVideoUrl: o.heroVideoUrl ?? site.heroVideoUrl,
  };
}
