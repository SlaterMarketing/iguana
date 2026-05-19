import { slugify } from "../lib/slug";
import type { Locale } from "../i18n/locale";

/** Editorial blurbs for /locations/[city] — keyed by slugified city strings. */
const blurbsRaw: Record<string, Record<Locale, string[]>> = {
  cancun: {
    en: [
      "Cancún anchors the Riviera run for headline tours and rotating guests—we keep english rooms tight, roomy, and on time.",
      "Expect international billings, bilingual hosting when needed, and rooms built for travellers who crave punchlines—not punch clocks.",
    ],
    es: [
      "Cancún es el ancla de la gira por la Riviera para headliners de paso y invitados rotativos: mantenemos las salas ágiles, amplias y puntuales.",
      "Espera carteleras internacionales, hosts bilingües cuando se necesita, y salas diseñadas para viajeros que buscan punchlines, no relojes checadores.",
    ],
  },
  "playa-del-carmen": {
    en: [
      "Playa is our weekly heartbeat: alternating showcases, curated open mics, and pop-up specials when tours swing through Quintana Roo.",
      "Venues zig-zag Centro to the fringe—bookmark this page whenever you bounce between Playa's coast and cenote day trips.",
    ],
    es: [
      "Playa es nuestro latido semanal: showcases alternos, open mics curados y especiales pop-up cuando las giras pasan por Quintana Roo.",
      "Las sedes van del Centro a la periferia: guarda esta página para cuando saltes entre la costa de Playa y tus días de cenotes.",
    ],
  },
  cozumel: {
    en: [
      "Island nights skew intimate: smaller capacities, cruisers mixed with dive-shop regulars, and comics who love riffing seaside audiences.",
      "Ferry commuters: check dates early—shows often sell faster than mainland rooms during high season swings.",
    ],
    es: [
      "Las noches de isla son íntimas: capacidades reducidas, cruceristas mezclados con locales de tiendas de buceo, y comediantes que aman improvisar con público frente al mar.",
      "Si tomas el ferry: revisa fechas con anticipación: los shows suelen agotarse más rápido que en la tierra firme en temporada alta.",
    ],
  },
  tulum: {
    en: [
      "Tulum skews traveller-heavy; we spotlight storytellers who can thread surf-town energy without losing mainland polish.",
      "When boutique hotels ping us for bilingual tastemaker rooms, these listings are usually the fastest path in.",
    ],
    es: [
      "Tulum tiene mucho turismo; destacamos storytellers que pueden canalizar la energía de pueblo surf sin perder el brillo de la ciudad.",
      "Cuando hoteles boutique nos buscan para salas bilingües, estas fechas suelen ser la entrada más rápida.",
    ],
  },
  merida: {
    en: [
      "Mérida's colonial streets pair well with cerebral sets—ideal for comedians itching for slower-burn audiences than beach clubs.",
      "We stagger shows around city festivals; sign up early if you already have festival tickets locked.",
    ],
    es: [
      "Las calles coloniales de Mérida combinan bien con sets cerebrales: ideal para comediantes que buscan públicos más pausados que los de beach clubs.",
      "Espaciamos shows alrededor de festivales de la ciudad; apúntate temprano si ya tienes boletos de festival.",
    ],
  },
  "puerto-morelos": {
    en: [
      "Puerto Morelos keeps things neighbourly—the perfect pit stop between Cancún airport hustle and cenote itineraries.",
      "Expect laid-back laughs, approachable pricing, and lineups sprinkled with Playa regulars swinging south for the night.",
    ],
    es: [
      "Puerto Morelos mantiene un ambiente vecinal: la parada perfecta entre el ajetreo del aeropuerto de Cancún y los itinerarios de cenotes.",
      "Expecta risas relajadas, precios accesibles y carteleras salpicadas con regulars de Playa que bajan por la noche.",
    ],
  },
  "puerto-aventuras": {
    en: [
      "Marina-town rooms lean resort-forward; we prioritise bilingual intros and tighter runtimes for family-heavy weeks.",
      "Great for marina residents who want headline energy without hauling into Centro traffic.",
    ],
    es: [
      "Las salas de pueblo marina son más resort; priorizamos intros bilingües y tiempos más ajustados en semanas familiares.",
      "Ideal para residentes de la marina que quieren energía de headliner sin meterse al tráfico del Centro.",
    ],
  },
};

export type CityBlurb = {
  paragraphs: string[];
};

export function getCityBlurb(locale: Locale, slug: string): CityBlurb | undefined {
  const key = slugify(slug);
  const entry = blurbsRaw[key];
  const paragraphs = entry?.[locale] ?? entry?.["en"];
  return paragraphs?.length ? { paragraphs } : undefined;
}
