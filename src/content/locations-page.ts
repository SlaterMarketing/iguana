/** Editorial content for /locations/ — aligned with the legacy Framer page. */

export const locationsPage = {
  heroTitle: "Comedy locations in Quintana Roo",
  intro:
    "Over the years, as we've grown, we've begun to offer comedy shows in more and more locations across Quintana Roo.",
  statsHeading: "Leading the comedy scene in the Mexican Caribbean",
  statsBody:
    "Iguana started with just one Mexican comedian looking for opportunity, realising it didn't exist, and starting to build it. After living in Chicago and getting back, he wanted to perform, and realised if he wanted that, he'd have to run the shows to do it.",
  galleryImages: [
    "https://images.unsplash.com/photo-1540039155733-5bb546b929d3?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?q=80&w=1200&auto=format&fit=crop",
  ],
  servicesBackground:
    "https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?q=80&w=2000&auto=format&fit=crop",
  heroTexture:
    "https://images.unsplash.com/photo-1507676184212-d03709172ecf?q=80&w=2000&auto=format&fit=crop",
} as const;

export type LocationCityCard = {
  slug: string;
  name: string;
  imageUrl: string;
};

export const locationCityCards: readonly LocationCityCard[] = [
  {
    slug: "cancun",
    name: "Cancun",
    imageUrl:
      "https://images.unsplash.com/photo-1510097466554-933fbc264fbc?q=80&w=1200&auto=format&fit=crop",
  },
  {
    slug: "cozumel",
    name: "Cozumel",
    imageUrl:
      "https://images.unsplash.com/photo-1551632436-7926d5c9809a?q=80&w=1200&auto=format&fit=crop",
  },
  {
    slug: "merida",
    name: "Merida",
    imageUrl:
      "https://images.unsplash.com/photo-1594771705619-57356a5c2b48?q=80&w=1200&auto=format&fit=crop",
  },
  {
    slug: "playa-del-carmen",
    name: "Playa del Carmen",
    imageUrl:
      "https://images.unsplash.com/photo-1519046904884-53103b34f206?q=80&w=1200&auto=format&fit=crop",
  },
  {
    slug: "puerto-aventuras",
    name: "Puerto Aventuras",
    imageUrl:
      "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1200&auto=format&fit=crop",
  },
  {
    slug: "puerto-morelos",
    name: "Puerto Morelos",
    imageUrl:
      "https://images.unsplash.com/photo-1544551763-46a013bb70d5?q=80&w=1200&auto=format&fit=crop",
  },
  {
    slug: "tulum",
    name: "Tulum",
    imageUrl:
      "https://images.unsplash.com/photo-1552733407-5d5c46c3bb3b?q=80&w=1200&auto=format&fit=crop",
  },
] as const;

export const locationServices = [
  {
    number: "01",
    title: "Stand up shows",
    body: "Iguana works to regularly bring the best comedy to Quintana Roo from all across the world, hosting shows that comedians are proud to perform at and audiences want to be a part of.",
    href: "/events/",
  },
  {
    number: "02",
    title: "Open mics",
    href: "/events/",
  },
  {
    number: "03",
    title: "Private corporate events",
    href: "/work-with-us/#private-events",
  },
  {
    number: "04",
    title: "Hotel and resort shows",
    href: "/work-with-us/#hotels",
  },
] as const;

/** Cities highlighted in the legacy stats strip (venue counts filled from API when available). */
export const locationStatsCities = [
  { slug: "cancun", name: "Cancun" },
  { slug: "tulum", name: "Tulum" },
  { slug: "merida", name: "Merida" },
  { slug: "playa-del-carmen", name: "Playa del Carmen" },
] as const;
