import type { KintanaPublicEvent } from "@kintana/sdk";

import type { Locale } from "../i18n/locale";
import { site } from "../content/site";
import { eventVenueLabel } from "./event-hero";

/**
 * What Google is told about the club and about each show.
 *
 * Two separate jobs. The club is a place with an address, a phone number and a map pin, which is what a local
 * search has to be able to answer; a show is an Event with a date, a price and a venue, which is what puts a
 * night into Google's event listings rather than into a plain blue link.
 *
 * Everything here is the same data the page already shows a human. Structured data that disagrees with the page
 * is worse than none: it is the one class of SEO mistake that gets a site penalised rather than ignored.
 */

/** Fixed offset. Quintana Roo is UTC-05:00 all year, which is why the whole site can treat it as a constant. */
const CANCUN_OFFSET = "-05:00";

export function venueAddressSchema() {
  const a = site.venuePostal;
  return {
    "@type": "PostalAddress",
    streetAddress: a.streetAddress,
    addressLocality: a.addressLocality,
    addressRegion: a.addressRegion,
    postalCode: a.postalCode,
    addressCountry: a.addressCountry,
  };
}

function venueGeo() {
  return { "@type": "GeoCoordinates", latitude: site.venuePostal.latitude, longitude: site.venuePostal.longitude };
}

/** The club itself, on every page. `ComedyClub` is a real schema.org type, so it beats a generic LocalBusiness. */
export function comedyClubSchema(origin: string, locale: Locale) {
  return {
    "@context": "https://schema.org",
    "@type": "ComedyClub",
    "@id": `${origin}/#venue`,
    name: site.name,
    url: origin,
    email: site.email,
    telephone: `+${site.whatsappE164}`,
    address: venueAddressSchema(),
    geo: venueGeo(),
    hasMap: site.venueMapsUrl,
    image: new URL(site.brandMomentImage, origin).toString(),
    sameAs: [site.instagramUrl, site.facebookUrl, site.linkedInUrl].filter(Boolean),
    inLanguage: [locale === "es" ? "es-MX" : "en-US"],
  };
}

/**
 * `YYYY-MM-DD` plus `HH:MM` as an instant in Cancun. Without the offset a search engine reads the time in its
 * own zone and can advertise a show on the wrong day.
 */
function instant(day: string, time?: string | null): string | null {
  const date = /^(\d{4}-\d{2}-\d{2})/.exec(day.trim())?.[1];
  if (!date) return null;
  const clock = /^(\d{2}:\d{2})/.exec((time ?? "").trim())?.[1];
  return clock ? `${date}T${clock}:00${CANCUN_OFFSET}` : date;
}

const STATUS = {
  "sold-out": "https://schema.org/EventScheduled",
  postponed: "https://schema.org/EventPostponed",
  cancelled: "https://schema.org/EventCancelled",
} as const;

/** One show. Omits anything the page does not actually know rather than guessing a value to fill the slot. */
export function eventSchema(event: KintanaPublicEvent, origin: string, pageUrl: string) {
  const start = instant(event.date, event.showTime);
  if (!start) return null;

  const free = event.priceFrom === 0;
  const offers = event.priceFrom != null
    ? {
        "@type": "Offer",
        url: pageUrl,
        price: (event.priceFrom / 100).toFixed(2),
        priceCurrency: (event.priceCurrency || "MXN").toUpperCase(),
        availability: event.status === "sold-out" ? "https://schema.org/SoldOut" : "https://schema.org/InStock",
        category: free ? "free" : undefined,
      }
    : undefined;

  const performers = (event.lineup ?? [])
    .map((member) => member.name)
    .filter(Boolean)
    .map((name) => ({ "@type": "Person", name }));

  return {
    "@context": "https://schema.org",
    "@type": "ComedyEvent",
    name: event.name,
    url: pageUrl,
    startDate: start,
    // Only when there IS an end time. Without one `instant` returns the bare date, which is midnight, which is
    // before the start and reads to a search engine as a show that ends four hours before it begins.
    ...(event.endTime?.trim() ? { endDate: instant(event.date, event.endTime) ?? undefined } : {}),
    // Nothing here is streamed, and saying so is what keeps a listing out of the online-events bucket.
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    eventStatus: STATUS[event.status as keyof typeof STATUS] ?? "https://schema.org/EventScheduled",
    inLanguage: event.language === "es" ? "es-MX" : "en-US",
    description: event.description || event.longDescription || undefined,
    image: event.imageUrl ? [event.imageUrl] : undefined,
    location: {
      "@type": "Place",
      name: eventVenueLabel(event) || site.name,
      address: event.venue?.address?.trim() || venueAddressSchema(),
      ...(event.venue?.lat != null && event.venue?.lng != null
        ? { geo: { "@type": "GeoCoordinates", latitude: event.venue.lat, longitude: event.venue.lng } }
        : {}),
    },
    organizer: { "@type": "Organization", name: site.name, url: origin },
    ...(performers.length ? { performer: performers } : {}),
    ...(offers ? { offers } : {}),
  };
}

/** Drops undefined values, which JSON.stringify keeps out of objects but Google reads as an error in arrays. */
export function jsonLd(value: unknown): string {
  return JSON.stringify(value, (_key, v) => (v === undefined ? undefined : v));
}
