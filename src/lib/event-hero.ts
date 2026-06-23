import type { KintanaPublicEvent } from "@kintana/sdk";
import type { Locale } from "../i18n/locale";
import { formatEventScheduleLine } from "./events";

export function eventHeroImageUrl(
  event: Pick<KintanaPublicEvent, "imageUrl" | "imageUrlMobile">
): string | null {
  return event.imageUrl?.trim() || event.imageUrlMobile?.trim() || null;
}

export function absoluteMediaUrl(url: string, siteOrigin: string): string {
  if (/^https?:\/\//i.test(url)) return url;
  const path = url.startsWith("/") ? url : `/${url}`;
  return `${siteOrigin.replace(/\/$/, "")}${path}`;
}

export function eventSocialDescription(
  event: KintanaPublicEvent,
  locale: Locale,
  fallback: string
): string {
  const raw =
    event.description?.trim() ||
    event.longDescription?.trim().split(/\r?\n\s*\r?\n/)[0]?.trim() ||
    "";

  if (raw) {
    const singleLine = raw.replace(/\s+/g, " ").trim();
    if (singleLine.length <= 300) return singleLine;
    const cut = singleLine.slice(0, 297);
    const lastSpace = cut.lastIndexOf(" ");
    return `${lastSpace > 200 ? cut.slice(0, lastSpace) : cut}…`;
  }

  const schedule = formatEventScheduleLine(event, locale);
  const venue = eventVenueLabel(event);
  const parts = [schedule, venue].filter(Boolean);
  return parts.length ? parts.join(" · ") : fallback;
}

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

/** Google Maps iframe embed — no API key; prefers coordinates when available. */
export function eventVenueMapEmbedUrl(
  event: Pick<KintanaPublicEvent, "venue" | "city">
): string | null {
  const venue = event.venue;
  if (venue?.lat != null && venue?.lng != null) {
    return `https://maps.google.com/maps?q=${venue.lat},${venue.lng}&z=15&output=embed`;
  }
  const query = venue?.address?.trim()
    ? `${venue.name?.trim() ? `${venue.name.trim()}, ` : ""}${venue.address.trim()}`
    : [venue?.name, event.city].filter(Boolean).join(", ");
  return query
    ? `https://maps.google.com/maps?q=${encodeURIComponent(query)}&t=&z=15&ie=UTF8&iwloc=&output=embed`
    : null;
}

export function eventVenueLabel(event: Pick<KintanaPublicEvent, "venue" | "city" | "country">): string {
  if (event.venue?.name?.trim()) return event.venue.name.trim();
  return [event.city, event.country].filter(Boolean).join(", ");
}
