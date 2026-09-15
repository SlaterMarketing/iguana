import type { Locale } from "../i18n/locale";

/**
 * Nights when the weekly open mics do not happen.
 *
 * The site renders every request on the server, so a closure disappears on its own once the last
 * date passes: no cron, no deploy, no "remember to take the banner down". Dates are Cancún calendar
 * days (`YYYY-MM-DD`), matching how the API reports event dates.
 */
interface Closure {
  dates: string[];
  copy: Record<Locale, { headline: string; headlineTonight: string; detail: string }>;
}

const CLOSURES: Closure[] = [
  {
    // Mexican Independence Day: El Grito on the 15th, the holiday itself on the 16th.
    dates: ["2026-09-15", "2026-09-16"],
    copy: {
      en: {
        headline: "No open mic tonight or tomorrow",
        headlineTonight: "No open mic tonight",
        detail: "We are closed for the Mexican Independence holiday. The open mics are back next Tuesday.",
      },
      es: {
        headline: "Sin open mic hoy ni mañana",
        headlineTonight: "Sin open mic hoy",
        detail: "Cerramos por las fiestas patrias. Los open mic regresan el próximo martes.",
      },
    },
  },
];

export function todayInCancun(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Cancun" }).format(now);
}

export interface HolidayNotice {
  headline: string;
  detail: string;
}

/** The notice to show today, or null once every date in the closure has passed. */
export function holidayNotice(locale: Locale, today: string = todayInCancun()): HolidayNotice | null {
  const closure = CLOSURES.find((entry) => entry.dates.includes(today));
  if (!closure) return null;

  const copy = closure.copy[locale];
  const remaining = closure.dates.filter((date) => date >= today);
  return {
    headline: remaining.length > 1 ? copy.headline : copy.headlineTonight,
    detail: copy.detail,
  };
}
