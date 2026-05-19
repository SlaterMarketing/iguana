/** Editorial content for /locations/ — aligned with the legacy Framer page. */

import { heroCityChoices } from "./site";

export const locationsPage = {
  heroTitle: "Comedy locations in Quintana Roo",
  heroImage:
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/8c3d112d09f2afd980eb02d754988b1f71eedfbb1638623ec5ee276784c55f41.webp",
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

const cityImages: Record<string, string> = {
  cancun:
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/a7f73321788a60c5e26fbc169098d29ca831a9fd8f81a1a4b04cb8f31b23905f.jpg",
  cozumel:
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/e3861e77e1377e8c41284752355ab7b3b815031fcb684553d4ecb115c3e792ed.jpg",
  merida:
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/e6864340e4c847c6212334eb852febdbbb5bbe872e2260a1801bb39b56491084.jpeg",
  "playa-del-carmen":
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/fc28c62ff25bfe59ab4a1b77d48f063eeba57ba8c4f7605211cfd701fa7c6d27.jpg",
  "puerto-aventuras":
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/3fbec67adea60b37a8f4d8334ef5c90cac31b8717922357a6d21e11ce078aa52.webp",
  "puerto-morelos":
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/b40c63c032e048fe72ac7292d97c87d62f92a2d1d17fa175bda8071c2d9f518e.jpg",
  tulum:
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/4b654104e25fb08b6a3271259adebe774fd8e016daf0801620df9d1b65ca22e9.jpg",
};

/** City cards in nav order — labels match the homepage city picker. */
export const locationCityCards: readonly LocationCityCard[] = heroCityChoices
  .filter((entry) => entry.slug)
  .map((entry) => ({
    slug: entry.slug,
    name: entry.label,
    imageUrl: cityImages[entry.slug] ?? cityImages.cancun,
  }));

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
    body: "Weekly and rotating open mics give local comics stage time and travellers a chance to catch fresh material before it hits the festival circuit.",
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
  { slug: "cancun", name: "Cancún" },
  { slug: "tulum", name: "Tulum" },
  { slug: "merida", name: "Mérida" },
  { slug: "playa-del-carmen", name: "Playa del Carmen" },
] as const;
