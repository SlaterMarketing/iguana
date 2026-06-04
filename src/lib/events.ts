import type { KintanaPublicEvent } from "@kintana/sdk";
import { slugify } from "./slug";
import { localizePath } from "../i18n/routes";
import type { Locale } from "../i18n/locale";

/** Best-effort city slug derived from ticketing rows. */
export function eventCitySlug(event: KintanaPublicEvent): string {
  return slugify(event.venue?.city ?? event.city);
}

/** On-site checkout route (hydrated by `data-kintana-widget` + `/_t/k.js`). */
export function eventTicketsPath(event: Pick<KintanaPublicEvent, "slug" | "id">, locale: Locale = "en"): string | null {
  const key = event.slug?.trim() || event.id?.trim();
  return key ? localizePath(locale, "eventTickets", { slug: key }) : null;
}

/** True when the event detail page can mount the embedded checkout widget. */
export function eventSupportsOnSiteCheckout(
  event: Pick<KintanaPublicEvent, "id" | "status">
): boolean {
  return Boolean(event.id?.trim()) && event.status !== "sold-out" && event.status !== "postponed";
}

export function sortEventsAscending(events: KintanaPublicEvent[]): KintanaPublicEvent[] {
  return [...events].sort((a, b) => parseEventTs(a.date) - parseEventTs(b.date));
}

export function sortEventsDescending(events: KintanaPublicEvent[]): KintanaPublicEvent[] {
  return [...events].sort((a, b) => parseEventTs(b.date) - parseEventTs(a.date));
}

/** Local midnight today — events before this count as past. */
export function startOfTodayMs(now = new Date()): number {
  return new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
}

export function isPastEvent(event: KintanaPublicEvent, nowMs = startOfTodayMs()): boolean {
  if (event.status === "cancelled") return false;
  if (event.status === "past") return true;
  const ts = parseEventTs(event.date);
  return Number.isFinite(ts) && ts < nowMs;
}

export function isUpcomingEvent(event: KintanaPublicEvent, nowMs = startOfTodayMs()): boolean {
  if (event.status === "cancelled") return false;
  if (event.status === "past") return false;
  const ts = parseEventTs(event.date);
  if (!Number.isFinite(ts)) return true;
  return ts >= nowMs;
}

export function partitionEventsBySchedule(events: readonly KintanaPublicEvent[]) {
  const nowMs = startOfTodayMs();
  const upcoming: KintanaPublicEvent[] = [];
  const past: KintanaPublicEvent[] = [];
  for (const event of events) {
    if (isPastEvent(event, nowMs)) past.push(event);
    else if (isUpcomingEvent(event, nowMs)) upcoming.push(event);
  }
  return { upcoming, past };
}

export function parseEventTs(isoLike: string): number {
  const t = Date.parse(isoLike);
  return Number.isFinite(t) ? t : Number.POSITIVE_INFINITY;
}

function ordinalDay(day: number): string {
  const mod100 = day % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${day}th`;
  switch (day % 10) {
    case 1:
      return `${day}st`;
    case 2:
      return `${day}nd`;
    case 3:
      return `${day}rd`;
    default:
      return `${day}th`;
  }
}

/** e.g. `2026-05-18` → `18th May, 2026` */
export function formatEventDate(dateInput: string, locale: Locale = "en"): string {
  const raw = dateInput.trim();
  const fmtLocale = locale === "es" ? "es-MX" : "en-GB";
  const isoDay = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  if (isoDay) {
    const year = Number(isoDay[1]);
    const monthIndex = Number(isoDay[2]) - 1;
    const day = Number(isoDay[3]);
    const month = new Intl.DateTimeFormat(fmtLocale, { month: "short" }).format(new Date(year, monthIndex, day));
    return locale === "es" ? `${day} ${month}, ${year}` : `${ordinalDay(day)} ${month}, ${year}`;
  }

  const t = Date.parse(raw);
  if (!Number.isFinite(t)) return dateInput;
  const d = new Date(t);
  const month = new Intl.DateTimeFormat(fmtLocale, { month: "short" }).format(d);
  return locale === "es" ? `${d.getDate()} ${month}, ${d.getFullYear()}` : `${ordinalDay(d.getDate())} ${month}, ${d.getFullYear()}`;
}

function getTimeFormatter(locale: Locale) {
  return new Intl.DateTimeFormat(locale === "es" ? "es-MX" : "en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

/** e.g. `15:00` → `3:00 PM` */
export function formatEventTime(timeInput: string | null | undefined, locale: Locale = "en"): string | null {
  if (!timeInput?.trim()) return null;
  const raw = timeInput.trim();
  const timeFormatter = getTimeFormatter(locale);

  if (/\b(am|pm)\b/i.test(raw)) {
    const d = new Date(`1970-01-01 ${raw}`);
    if (!Number.isNaN(d.getTime())) return timeFormatter.format(d);
    return raw;
  }

  const clock = /^(\d{1,2}):(\d{2})(?::\d{2})?$/.exec(raw);
  if (clock) {
    const hours24 = Number(clock[1]);
    const minutes = Number(clock[2]);
    if (hours24 > 23 || minutes > 59) return raw;
    const period = hours24 >= 12 ? "PM" : "AM";
    const hours12 = hours24 % 12 || 12;
    return `${hours12}:${String(minutes).padStart(2, "0")} ${period}`;
  }

  const parsed = Date.parse(raw);
  if (Number.isFinite(parsed)) return timeFormatter.format(new Date(parsed));

  return raw;
}

export function formatEventScheduleLine(
  event: Pick<KintanaPublicEvent, "date" | "doorsOpen" | "showTime">,
  locale: Locale = "en"
): string {
  const parts = [formatEventDate(event.date, locale)];
  const doors = formatEventTime(event.doorsOpen, locale);
  const show = formatEventTime(event.showTime, locale);
  if (doors) parts.push(locale === "es" ? `puertas ${doors}` : `doors ${doors}`);
  if (show) parts.push(locale === "es" ? `show ${show}` : `show ${show}`);
  return parts.join(" · ");
}

/** Formatted money from ticketing minor units (`priceFrom`) when present on the event payload. */
export function formatMinorUnitsPrice(
  event: Pick<KintanaPublicEvent, "priceFrom" | "priceCurrency">,
  locale: Locale = "en"
): string | null {
  if (event.priceFrom == null) return null;
  const currency = event.priceCurrency?.trim() || "USD";
  const major = event.priceFrom / 100;
  try {
    return new Intl.NumberFormat(locale === "es" ? "es-MX" : "en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: major % 1 === 0 ? 0 : 2,
    }).format(major);
  } catch {
    return `${major % 1 === 0 ? major.toFixed(0) : major.toFixed(2)} ${currency}`;
  }
}

/** Returns "Month YYYY" in locale. */
export function monthLabel(dateInput: string, locale: Locale = "en"): string {
  const d = Date.parse(dateInput);
  if (!Number.isFinite(d)) return locale === "es" ? "Pronto" : "Soon";
  return new Intl.DateTimeFormat(locale === "es" ? "es-MX" : "en-US", { month: "long", year: "numeric" }).format(new Date(d));
}

export function groupEventsByMonth(
  events: KintanaPublicEvent[],
  order: "asc" | "desc" = "asc",
  locale: Locale = "en"
): Map<string, KintanaPublicEvent[]> {
  const sorted = order === "desc" ? sortEventsDescending(events) : sortEventsAscending(events);
  const map = new Map<string, KintanaPublicEvent[]>();
  for (const event of sorted) {
    const bucket = monthLabel(event.date, locale);
    const row = map.get(bucket) ?? [];
    row.push(event);
    map.set(bucket, row);
  }
  return map;
}
