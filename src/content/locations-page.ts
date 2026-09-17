/** Editorial content for /locations/, aligned with the legacy Framer page. */

import { heroCityChoices } from "./site";
import { localizePath } from "../i18n/routes";
import type { Locale } from "../i18n/locale";

export function getLocationsPage(locale: Locale) {
  const isES = locale === "es";
  return {
    heroTitle: isES
      ? "Sedes de comedia en Quintana Roo"
      : "Comedy locations in Quintana Roo",
    heroImage:
      "/media/locations-hero.webp",
    intro: isES
      ? "A lo largo de los años, a medida que hemos crecido, hemos comenzado a ofrecer shows de comedia en más y más ubicaciones en Quintana Roo."
      : "Over the years, as we've grown, we've begun to offer comedy shows in more and more locations across Quintana Roo.",
    statsHeading: isES
      ? "Liderando la escena de comedia en el Caribe Mexicano"
      : "Leading the comedy scene in the Mexican Caribbean",
    statsBody: isES
      ? "Iguana comenzó con un solo comediante mexicano buscando oportunidad, dándose cuenta de que no existía, y empezando a construirla. Después de vivir en Chicago y regresar, quería presentarse, y se dio cuenta de que si quería eso, tendría que organizar los shows para lograrlo."
      : "Iguana started with just one Mexican comedian looking for opportunity, realising it didn't exist, and starting to build it. After living in Chicago and getting back, he wanted to perform, and realised if he wanted that, he'd have to run the shows to do it.",
    galleryImages: [
      "/media/club-photo.webp",
      "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?q=80&w=1200&auto=format&fit=crop",
      "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?q=80&w=1200&auto=format&fit=crop",
    ],
    servicesBackground:
      "https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?q=80&w=2000&auto=format&fit=crop",
    heroTexture:
      "https://images.unsplash.com/photo-1507676184212-d03709172ecf?q=80&w=2000&auto=format&fit=crop",
  } as const;
}

export type LocationCityCard = {
  slug: string;
  name: string;
  imageUrl: string;
};

const cityImages: Record<string, string> = {
  cancun:
    "/media/city-cancun.jpg",
  cozumel:
    "/media/city-cozumel.jpg",
  merida:
    "/media/city-merida.jpeg",
  "playa-del-carmen":
    "/media/city-playa-del-carmen.jpg",
  "puerto-aventuras":
    "/media/city-puerto-aventuras.webp",
  "puerto-morelos":
    "/media/city-puerto-morelos.jpg",
  tulum:
    "/media/city-tulum.jpg",
};

/** City cards in nav order: labels match the homepage city picker. */
export const locationCityCards: readonly LocationCityCard[] = heroCityChoices
  .filter((entry) => entry.slug)
  .map((entry) => ({
    slug: entry.slug,
    name: entry.label,
    imageUrl: cityImages[entry.slug] ?? cityImages.cancun,
  }));

export function getLocationServices(locale: Locale) {
  const isES = locale === "es";
  return [
    {
      number: "01",
      title: isES ? "Shows de stand up" : "Stand up shows",
      body: isES
        ? "Iguana trabaja para traer regularmente la mejor comedia a Quintana Roo de todo el mundo, organizando shows de los que los comediantes están orgullosos de participar y el público quiere ser parte."
        : "Iguana works to regularly bring the best comedy to Quintana Roo from all across the world, hosting shows that comedians are proud to perform at and audiences want to be a part of.",
      href: localizePath(isES ? "es" : "en", "events"),
    },
    {
      number: "02",
      title: isES ? "Open mics" : "Open mics",
      body: isES
        ? "Open mics semanales y rotativos dan tiempo de escenario a cómicos locales y a viajeros la oportunidad de ver material fresco antes de que llegue al circuito de festivales."
        : "Weekly and rotating open mics give local comics stage time and travellers a chance to catch fresh material before it hits the festival circuit.",
      href: localizePath(isES ? "es" : "en", "events"),
    },
    {
      number: "03",
      title: isES ? "Eventos privados corporativos" : "Private corporate events",
      href: localizePath(isES ? "es" : "en", "workWithUs") + "#private-events",
    },
    {
      number: "04",
      title: isES ? "Shows para hoteles y resorts" : "Hotel and resort shows",
      href: localizePath(isES ? "es" : "en", "hotelsAndResorts"),
    },
  ] as const;
}

/** Cities highlighted in the legacy stats strip (venue counts filled from API when available). */
export const locationStatsCities = [
  { slug: "cancun", name: "Cancún" },
  { slug: "tulum", name: "Tulum" },
  { slug: "merida", name: "Mérida" },
  { slug: "playa-del-carmen", name: "Playa del Carmen" },
] as const;
