import { getCityBlurb } from "./city-blurbs";
import { locationCityCards } from "./locations-page";
import { heroCityChoices, site } from "./site";

export type CityLanding = {
  slug: string;
  label: string;
  heroImage: string;
  eyebrow: string;
  experienceHeading: string;
  experienceCopy: string;
};

export function getCityLanding(slug: string): CityLanding | undefined {
  const choice = heroCityChoices.find((entry) => entry.slug === slug);
  if (!choice || !choice.slug.length) return undefined;

  const card = locationCityCards.find((entry) => entry.slug === slug);
  const blurb = getCityBlurb(slug);
  const label = choice.label;

  return {
    slug,
    label,
    heroImage: card?.imageUrl ?? site.heroImage,
    eyebrow: `Live English comedy in ${label}`,
    experienceHeading: `The iguana experience in ${label}`,
    experienceCopy:
      blurb?.paragraphs[0] ??
      `English stand-up across ${label}—curated showcases, touring headliners, and rooms built for travellers who want punchlines between beach days.`,
  };
}

export function listCityLandingSlugs(): string[] {
  return heroCityChoices.map((entry) => entry.slug).filter(Boolean);
}
