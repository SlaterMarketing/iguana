import { createKintanaClient } from "@kintana/sdk";
import type { KintanaPublicArtistEmbed, KintanaPublicEvent } from "@kintana/sdk";

import { eventCitySlug, sortEventsAscending } from "./events";
import { getKintanaEnv } from "./kintana-env";
import { logKintanaError, logKintanaSuccess } from "./kintana-error";

export type HomePageData = {
  hasCredentials: boolean;
  eventsPool: KintanaPublicEvent[];
  artistsPool: KintanaPublicArtistEmbed[];
  eventsCatalogFailed: boolean;
  performersCatalogFailed: boolean;
  trimmedEvents: KintanaPublicEvent[];
  wallArtists: KintanaPublicArtistEmbed[];
};

/** `YYYY-MM-DD` for today in Quintana Roo, where every show happens. */
function todayInCancun(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Cancun" }).format(now);
}

export async function loadHomePageData(citySlug?: string): Promise<HomePageData> {
  const { apiKey, baseUrl, hasCredentials } = getKintanaEnv();

  let eventsPool: KintanaPublicEvent[] = [];
  let artistsPool: KintanaPublicArtistEmbed[] = [];
  let eventsCatalogFailed = false;
  let performersCatalogFailed = false;

  if (hasCredentials) {
    const client = createKintanaClient({ apiKey, baseUrl });

    try {
      eventsPool = await client.listEvents({ limit: 40, from: todayInCancun() });
      logKintanaSuccess("listEvents", eventsPool.length);
    } catch (err) {
      logKintanaError("listEvents", err);
      eventsCatalogFailed = true;
      eventsPool = [];
    }

    try {
      artistsPool = await client.listArtists({ limit: 36 });
      logKintanaSuccess("listArtists", artistsPool.length);
    } catch (err) {
      logKintanaError("listArtists", err);
      performersCatalogFailed = true;
      artistsPool = [];
    }
  }

  const slug = citySlug?.trim() ?? "";
  // The API marks a show "past" once its day has ended in Cancún, so this holds whatever timezone the server runs in.
  let cityFiltered = sortEventsAscending(
    eventsPool.filter((evt) => evt.status !== "cancelled" && evt.status !== "past"),
  );
  if (slug.length) {
    cityFiltered = cityFiltered.filter((evt) => eventCitySlug(evt) === slug);
  }

  const prioritized = [
    ...cityFiltered.filter((evt) => evt.status === "on-sale"),
    ...cityFiltered.filter((evt) => evt.status !== "on-sale"),
  ];

  return {
    hasCredentials,
    eventsPool,
    artistsPool,
    eventsCatalogFailed,
    performersCatalogFailed,
    trimmedEvents: prioritized.slice(0, 6),
    wallArtists: artistsPool.slice(0, 3),
  };
}
