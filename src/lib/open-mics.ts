import type { KintanaPublicEvent } from "@kintana/sdk";

import type { Locale } from "../i18n/locale";
import { sortEventsAscending } from "./events";

/** Set on the weekly open mic nights by `manage.py setup_open_mics`. */
export const OPEN_MIC_TAG = "open-mic";

export function isOpenMic(evt: KintanaPublicEvent): boolean {
  return (evt.tags ?? []).includes(OPEN_MIC_TAG);
}

/**
 * The next night that can still be reserved in each language. A sold-out Tuesday is skipped in favour of the
 * following one, so a Reserve button never lands on a night with no seats left.
 */
export function nextBookableOpenMics(events: KintanaPublicEvent[]): { es?: KintanaPublicEvent; en?: KintanaPublicEvent } {
  const bookable = sortEventsAscending(events.filter((evt) => isOpenMic(evt) && evt.status === "on-sale"));
  return {
    es: bookable.find((evt) => evt.language === "es"),
    en: bookable.find((evt) => evt.language === "en"),
  };
}

/** 5000 MXN -> "50 MXN". The shared formatMinorUnitsPrice prints the currency twice ("MX$50MXN"). */
export function formatSeatPrice(evt: KintanaPublicEvent, locale: Locale): string {
  if (evt.priceFrom == null) return "";
  const amount = new Intl.NumberFormat(locale === "es" ? "es-MX" : "en-US", { maximumFractionDigits: 2 }).format(
    evt.priceFrom / 100,
  );
  return `${amount} ${(evt.priceCurrency ?? "").toUpperCase()}`.trim();
}
