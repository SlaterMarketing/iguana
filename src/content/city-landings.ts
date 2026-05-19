import { getCityBlurb } from "./city-blurbs";
import { locationCityCards } from "./locations-page";
import { heroCityChoices, site } from "./site";
import type { Locale } from "../i18n/locale";

export type CityLanding = {
  slug: string;
  label: string;
  heroImage: string;
  eyebrow: string;
  experienceHeading: string;
  experienceCopy: string;
};

export function getCityLanding(locale: Locale, slug: string): CityLanding | undefined {
  const choice = heroCityChoices.find((entry) => entry.slug === slug);
  if (!choice || !choice.slug.length) return undefined;

  const card = locationCityCards.find((entry) => entry.slug === slug);
  const blurb = getCityBlurb(locale, slug);
  const label = choice.label;

  const isES = locale === "es";

  return {
    slug,
    label,
    heroImage: card?.imageUrl ?? site.heroImage,
    eyebrow: isES
      ? `Comedia en vivo en inglés en ${label}`
      : `Live English comedy in ${label}`,
    experienceHeading: isES
      ? `La experiencia Iguana en ${label}`
      : `The iguana experience in ${label}`,
    experienceCopy:
      blurb?.paragraphs[0] ??
      (isES
        ? `Stand-up en inglés en ${label}: showcases curados, headliners de gira y salas diseñadas para viajeros que quieren punchlines entre días de playa.`
        : `English stand-up across ${label}—curated showcases, touring headliners, and rooms built for travellers who want punchlines between beach days.`),
  };
}

export function listCityLandingSlugs(): string[] {
  return heroCityChoices.map((entry) => entry.slug).filter(Boolean);
}
