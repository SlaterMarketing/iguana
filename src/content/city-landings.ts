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
      ? `Stand-up en vivo en español e inglés en ${label}`
      : `Live stand-up in English and Spanish in ${label}`,
    experienceHeading: isES
      ? `La experiencia Iguana en ${label}`
      : `The iguana experience in ${label}`,
    experienceCopy:
      blurb?.paragraphs[0] ??
      (isES
        ? `Stand-up en español e inglés en ${label}: showcases, comediantes de gira y noches para locales y viajeros por igual.`
        : `Stand-up in English and Spanish in ${label}: curated showcases, touring headliners and nights for locals and travellers alike.`),
  };
}

export function listCityLandingSlugs(): string[] {
  return heroCityChoices.map((entry) => entry.slug).filter(Boolean);
}
