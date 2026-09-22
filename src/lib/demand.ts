import type { KintanaPublicEvent } from "@kintana/sdk";

import type { Locale } from "../i18n/locale";
import { t } from "../i18n/ui";

/**
 * How full a night is, and how fast it is filling. The API sends this on every event (see
 * `backend/sales/demand.py`), and the checkout iframe already prints the same three sentences from the same
 * numbers. This is the site's copy of that, so a person sees one consistent story from the home page hero to
 * the reserve button.
 *
 * Urgency is only persuasive while it is true, so every rule that keeps it honest lives in the backend and is
 * reproduced here rather than loosened: the window is the tightest one that genuinely holds the bookings, a
 * count below two is not shown at all, and an empty room says nothing rather than something weak.
 */
export type EventDemand = {
  capacity: number;
  taken: number;
  left: number;
  showBar: boolean;
  recent: number;
  /** The English window key the backend chose; both languages map it through `WINDOW_KEYS`. */
  recentWindow: string;
};

/** The SDK's event type is fixed and does not know about this field, so read it off the payload by hand. */
export function eventDemand(evt: KintanaPublicEvent): EventDemand | null {
  const raw = (evt as unknown as { demand?: unknown }).demand;
  if (!raw || typeof raw !== "object") return null;
  const d = raw as Partial<EventDemand>;
  if (!d.capacity || typeof d.capacity !== "number") return null;
  return {
    capacity: d.capacity,
    taken: Number(d.taken ?? 0),
    left: Number(d.left ?? 0),
    showBar: Boolean(d.showBar),
    recent: Number(d.recent ?? 0),
    recentWindow: String(d.recentWindow ?? ""),
  };
}

const WINDOW_KEYS = {
  "in the last hour": "demand.window.hour",
  "in the last few hours": "demand.window.hours",
  "in the last day": "demand.window.day",
} as const;

export type DemandLine = {
  text: string;
  /** Genuinely nearly gone, so the line is worth colouring. */
  tight: boolean;
  /** 0-100, or null when the room is too empty for a bar to be anything but discouraging. */
  fill: number | null;
};

/**
 * The one sentence worth saying about this night, or null when there is nothing honest to say.
 *
 * Order matters: seats running out beats somebody else booking, which beats a plain count. Each rung is a
 * weaker argument than the one above it, and the bottom rung is silence.
 */
export function demandLine(evt: KintanaPublicEvent, locale: Locale): DemandLine | null {
  const d = eventDemand(evt);
  if (!d) return null;

  const tight = d.left > 0 && d.left <= 10;
  let text = "";
  if (tight) {
    text = t(locale, "demand.left", { count: String(d.left), total: String(d.capacity) });
  } else if (d.recent >= 2 && d.recentWindow in WINDOW_KEYS) {
    const when = t(locale, WINDOW_KEYS[d.recentWindow as keyof typeof WINDOW_KEYS]);
    text = t(locale, "demand.recent", { count: String(d.recent), window: when });
  } else if (d.showBar) {
    text = t(locale, "demand.taken", { taken: String(d.taken), total: String(d.capacity) });
  }
  if (!text) return null;

  return { text, tight, fill: d.showBar ? Math.min(100, Math.round((d.taken / d.capacity) * 100)) : null };
}

/** Tightest first, matching WINDOWS in `backend/sales/demand.py`. */
const WINDOW_ORDER = ["in the last hour", "in the last few hours", "in the last day"];

/**
 * One sentence about the open mics as a whole, rather than one per night.
 *
 * The hero offers two nights side by side, and a line under each of them ("Tue · 2 people reserved in the last
 * few hours", "Wed · 3 people reserved in the last few hours") says the same thing twice and reads as filler.
 * Added together it is a bigger number, one line, and the same fact.
 *
 * When the nights sit in different windows the WIDER one is used, which understates rather than overstates: two
 * people who booked in the last hour also booked in the last day, so the sentence stays true.
 */
export function combinedRecentLine(events: KintanaPublicEvent[], locale: Locale): string | null {
  const counted = events
    .map(eventDemand)
    .filter((d): d is EventDemand => Boolean(d) && d!.recent >= 2 && WINDOW_ORDER.includes(d!.recentWindow));
  if (!counted.length) return null;

  const total = counted.reduce((sum, d) => sum + d.recent, 0);
  const widest = counted.reduce((worst, d) => Math.max(worst, WINDOW_ORDER.indexOf(d.recentWindow)), 0);
  const window = t(locale, WINDOW_KEYS[WINDOW_ORDER[widest] as keyof typeof WINDOW_KEYS]);
  return t(locale, "demand.recent", { count: String(total), window });
}
