import type { Locale } from "../i18n/locale";

/**
 * How far each city is from the club in Playa del Carmen, for the "no shows here yet" message on city pages.
 * Rounded, typical travel times: shown as "about", never as a promise.
 */
const TRAVEL_TO_PLAYA: Record<string, Record<Locale, string>> = {
  cancun: { en: "about an hour's drive away", es: "a más o menos una hora en auto" },
  "puerto-morelos": { en: "about 30 minutes' drive away", es: "a unos 30 minutos en auto" },
  "puerto-aventuras": { en: "about 20 minutes' drive away", es: "a unos 20 minutos en auto" },
  tulum: { en: "about an hour's drive away", es: "a más o menos una hora en auto" },
  cozumel: { en: "about 45 minutes away by ferry", es: "a unos 45 minutos en ferry" },
  merida: { en: "about 4 hours' drive away", es: "a unas 4 horas en auto" },
};

export function travelToPlaya(locale: Locale, citySlug: string): string {
  return TRAVEL_TO_PLAYA[citySlug]?.[locale] ?? (locale === "es" ? "muy cerca" : "not far away");
}
