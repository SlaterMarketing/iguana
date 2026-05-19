import { createKintanaClient } from "@kintana/sdk";
import type { KintanaPublicArtistEmbed, KintanaPublicEvent } from "@kintana/sdk";

import { eventCitySlug, sortEventsAscending } from "./events";
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

export async function loadHomePageData(citySlug?: string): Promise<HomePageData> {
  const apiKey = import.meta.env.PUBLIC_KINTANA_API_KEY as string | undefined;
  const baseUrl = import.meta.env.PUBLIC_KINTANA_BASE_URL as string | undefined;
  const hasCredentials = Boolean(apiKey?.trim() && baseUrl?.trim());

  let eventsPool: KintanaPublicEvent[] = [];
  let artistsPool: KintanaPublicArtistEmbed[] = [];
  let eventsCatalogFailed = false;
  let performersCatalogFailed = false;

  if (hasCredentials) {
    const client = createKintanaClient({ apiKey, baseUrl });

    try {
      eventsPool = await client.listEvents({ limit: 40 });
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
  let cityFiltered = sortEventsAscending(eventsPool.filter((evt) => evt.status !== "cancelled"));
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
    wallArtists: artistsPool.slice(0, 6),
  };
}
