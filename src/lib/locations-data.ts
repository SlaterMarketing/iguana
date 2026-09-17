import { createKintanaClient } from "@kintana/sdk";
import type { KintanaGroupedCity, KintanaPublicEvent, KintanaPublicVenueListed } from "@kintana/sdk";
import { groupVenuesByCity } from "@kintana/sdk/locations";

import { eventCitySlug, sortEventsAscending, todayInCancun } from "./events";
import { logKintanaError, logKintanaSuccess } from "./kintana-error";
import { getKintanaEnv } from "./kintana-env";
import { slugify } from "./slug";

export type LocationsCatalog = {
  grouped: KintanaGroupedCity[];
  venueCountBySlug: Map<string, number>;
  upcomingCountBySlug: Map<string, number>;
  artistCount: number;
  eventCount: number;
  venuesRequestFailed: boolean;
  hasCredentials: boolean;
};

const emptyCatalog = (): LocationsCatalog => ({
  grouped: [],
  venueCountBySlug: new Map(),
  upcomingCountBySlug: new Map(),
  artistCount: 0,
  eventCount: 0,
  venuesRequestFailed: false,
  hasCredentials: false,
});

function indexVenueCounts(grouped: KintanaGroupedCity[]) {
  const venueCountBySlug = new Map<string, number>();
  for (const group of grouped) {
    const slug = slugify(group.city);
    if (slug !== "unknown") venueCountBySlug.set(slug, group.venues.length);
  }
  return venueCountBySlug;
}

function indexUpcomingCounts(events: KintanaPublicEvent[]) {
  const upcomingCountBySlug = new Map<string, number>();
  for (const evt of events) {
    // The API marks a show "past" once its day has ended in Cancún; comparing against the server clock is not safe.
    if (evt.status === "cancelled" || evt.status === "past") continue;
    const slug = eventCitySlug(evt);
    if (!slug || slug === "unknown") continue;
    upcomingCountBySlug.set(slug, (upcomingCountBySlug.get(slug) ?? 0) + 1);
  }
  return upcomingCountBySlug;
}

export async function loadLocationsCatalog(): Promise<LocationsCatalog> {
  const { apiKey, baseUrl, hasCredentials } = getKintanaEnv();
  if (!hasCredentials) return emptyCatalog();

  const client = createKintanaClient({ apiKey, baseUrl });
  const catalog = emptyCatalog();
  catalog.hasCredentials = true;

  try {
    const venues = await client.listVenues();
    catalog.grouped = groupVenuesByCity(venues);
    catalog.venueCountBySlug = indexVenueCounts(catalog.grouped);
    logKintanaSuccess(`listVenues locations catalog (${catalog.grouped.length} cities)`, venues.length);
  } catch (err) {
    logKintanaError("listVenues locations catalog", err);
    catalog.venuesRequestFailed = true;
  }

  try {
    const artists = await client.listArtists({ limit: 200 });
    catalog.artistCount = artists.length;
  } catch {
    catalog.artistCount = 0;
  }

  let events: KintanaPublicEvent[] = [];
  try {
    events = await client.listEvents({ limit: 200 });
    catalog.eventCount = events.filter((evt) => evt.status !== "cancelled").length;
    // Count upcoming shows from their own request: the unfiltered list starts at the oldest events, so once there are
    // more than `limit` of them it would contain no upcoming shows at all.
    catalog.upcomingCountBySlug = indexUpcomingCounts(await client.listEvents({ limit: 200, from: todayInCancun() }));
  } catch {
    catalog.eventCount = 0;
    catalog.upcomingCountBySlug = new Map();
  }

  return catalog;
}

export type CityLocationsData = {
  venuesInCity: readonly KintanaPublicVenueListed[];
  happenings: KintanaPublicEvent[];
  venueCount: number;
  upcomingCount: number;
};

export async function loadCityLocationsData(citySlug: string): Promise<CityLocationsData> {
  const empty: CityLocationsData = {
    venuesInCity: [],
    happenings: [],
    venueCount: 0,
    upcomingCount: 0,
  };

  const { apiKey, baseUrl, hasCredentials } = getKintanaEnv();
  if (!hasCredentials) return empty;

  const client = createKintanaClient({ apiKey, baseUrl });

  try {
    const grouped = groupVenuesByCity(await client.listVenues());
    const match = grouped.find((group) => slugify(group.city) === citySlug);
    empty.venuesInCity = match?.venues ?? [];
    empty.venueCount = empty.venuesInCity.length;
  } catch {
    /* keep empty */
  }

  try {
    // Only today onward: without `from` this listed a city's oldest past shows under "Upcoming in <city>", and a city
    // with nothing coming up never reached the "no shows yet" message.
    const pool = sortEventsAscending(await client.listEvents({ limit: 140, from: todayInCancun() })).filter(
      (evt) => evt.status !== "cancelled" && evt.status !== "past",
    );
    const inCity = pool.filter((evt) => eventCitySlug(evt) === citySlug);
    empty.upcomingCount = inCity.length;
    empty.happenings = inCity.slice(0, 8);
  } catch {
    /* keep empty */
  }

  return empty;
}
