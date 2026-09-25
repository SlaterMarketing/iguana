import type { KintanaPublicEvent } from "@kintana/sdk";

import { sortEventsAscending, todayInCancun } from "./events";
import { createLocalizedKintanaClient, getKintanaEnv } from "./kintana-env";
import { logKintanaError, logKintanaSuccess } from "./kintana-error";
import type { Locale } from "../i18n/locale";

/**
 * The next nights somebody can actually still get into.
 *
 * A sold-out page is the one page on this site where the visitor has already decided to come out and has just
 * been told no. Sending them away with a sentence about open mics being free "every Tuesday and Wednesday"
 * asks them to go and find the date themselves, and most will not. A dated, clickable list is the difference
 * between a lost visit and a different one.
 *
 * 🚨 Filtered on `status`, never on a seat count. A night can be full at 40 of 80 on our own rows because a
 * guest promoter sells a block we never see, which is exactly how this page came to be sold out: offering a
 * night that is itself gone would repeat the insult.
 */
export async function stillOnSale(exceptId: string, locale: Locale, limit = 3): Promise<KintanaPublicEvent[]> {
  const { hasCredentials } = getKintanaEnv();
  if (!hasCredentials) return [];

  try {
    const pool = await createLocalizedKintanaClient(locale).listEvents({ limit: 40, from: todayInCancun() });
    logKintanaSuccess("listEvents", pool.length);
    return sortEventsAscending(pool)
      .filter((event) => event.id !== exceptId && event.status === "on-sale")
      .slice(0, limit);
  } catch (err) {
    // Never fatal: the sold-out answer itself is what the page owes the reader, and a list of alternatives is
    // a kindness on top of it. A catalogue failure must not take the answer down with it.
    logKintanaError("listEvents", err);
    return [];
  }
}
