import type { KintanaPublicEvent } from "@kintana/sdk";
import type { Locale } from "../i18n/locale";

export function formatEventHeroDateParts(dateInput: string, locale: Locale = "en") {
  const raw = dateInput.trim();
  const fmtLocale = locale === "es" ? "es-MX" : "en-GB";
  let d: Date;
  const isoDay = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  if (isoDay) {
    d = new Date(Number(isoDay[1]), Number(isoDay[2]) - 1, Number(isoDay[3]));
  } else {
    const t = Date.parse(raw);
    if (!Number.isFinite(t)) return null;
    d = new Date(t);
  }
  return {
    weekday: new Intl.DateTimeFormat(fmtLocale, { weekday: "short" }).format(d),
    day: String(d.getDate()),
    month: new Intl.DateTimeFormat(fmtLocale, { month: "short" }).format(d),
  };
}

/** Split "Performer - Show title" style names like Kintana event pages. */
export function splitEventDisplayTitle(name: string): { headline: string; subtitle: string | null } {
  const parts = name.split(/\s+[–—-]\s+/);
  if (parts.length >= 2) {
    return {
      headline: parts[0]!.trim(),
      subtitle: parts.slice(1).join(" – ").trim() || null,
    };
  }
  return { headline: name.trim(), subtitle: null };
}

export function eventVenueMapsUrl(
  event: Pick<KintanaPublicEvent, "venue" | "city">
): string | null {
  const venue = event.venue;
  if (venue?.lat != null && venue?.lng != null) {
    return `https://www.google.com/maps/search/?api=1&query=${venue.lat},${venue.lng}`;
  }
  const query = [venue?.address, venue?.name, event.city].filter(Boolean).join(", ");
  return query ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}` : null;
}

export function eventVenueLabel(event: Pick<KintanaPublicEvent, "venue" | "city" | "country">): string {
  if (event.venue?.name?.trim()) return event.venue.name.trim();
  return [event.city, event.country].filter(Boolean).join(", ");
}
