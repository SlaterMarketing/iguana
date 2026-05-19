import { slugify } from "../lib/slug";

/** Editorial blurbs for /locations/[city] — keyed by slugified english city strings. */
const blurbsRaw: Record<string, string[]> = {
  cancun: [
    "Cancún anchors the Riviera run for headline tours and rotating guests—we keep english rooms tight, roomy, and on time.",
    "Expect international billings, bilingual hosting when needed, and rooms built for travellers who crave punchlines—not punch clocks.",
  ],
  "playa-del-carmen": [
    "Playa is our weekly heartbeat: alternating showcases, curated open mics, and pop-up specials when tours swing through Quintana Roo.",
    "Venues zig-zag Centro to the fringe—bookmark this page whenever you bounce between Playa’s coast and cenote day trips.",
  ],
  cozumel: [
    "Island nights skew intimate: smaller capacities, cruisers mixed with dive-shop regulars, and comics who love riffing seaside audiences.",
    "Ferry commuters: check dates early—shows often sell faster than mainland rooms during high season swings.",
  ],
  tulum: [
    "Tulum skews traveller-heavy; we spotlight storytellers who can thread surf-town energy without losing mainland polish.",
    "When boutique hotels ping us for bilingual tastemaker rooms, these listings are usually the fastest path in.",
  ],
  merida: [
    "Mérida’s colonial streets pair well with cerebral sets—ideal for comedians itching for slower-burn audiences than beach clubs.",
    "We stagger shows around city festivals; sign up early if you already have festival tickets locked.",
  ],
  "puerto-morelos": [
    "Puerto Morelos keeps things neighbourly—the perfect pit stop between Cancún airport hustle and cenote itineraries.",
    "Expect laid-back laughs, approachable pricing, and lineups sprinkled with Playa regulars swinging south for the night.",
  ],
  "puerto-aventuras": [
    "Marina-town rooms lean resort-forward; we prioritise bilingual intros and tighter runtimes for family-heavy weeks.",
    "Great for marina residents who want headline energy without hauling into Centro traffic.",
  ],
};

export type CityBlurb = {
  paragraphs: string[];
};

export function getCityBlurb(slug: string): CityBlurb | undefined {
  const key = slugify(slug);
  const paragraphs = blurbsRaw[key];
  return paragraphs?.length ? { paragraphs } : undefined;
}
