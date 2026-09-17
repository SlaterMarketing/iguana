/**
 * Editorial copy & brand contacts — tweak here without chasing UI internals.
 */

export const site = {
  name: "Iguana Comedy",
  email: "hello@iguanacomedy.com",
  venueAddress: "Calle 6 Nte 189, Centro, 77710 Playa del Carmen, Q.R., Mexico",
  venueMapsUrl:
    "https://www.google.com/maps/search/?api=1&query=Iguana%20Comedy%2C%20Calle%206%20Nte%20189%2C%20Centro%2C%2077710%20Playa%20del%20Carmen%2C%20Q.R.%2C%20Mexico",
  /** Full international display (WhatsApp widget text) */
  whatsappDisplay: "+52 998 937 0209",
  /**
   * Digits only, for wa.me links. Must be the same number as whatsappDisplay: the Framer-era site linked
   * 52 988 937 0209 (988, a typo), so every WhatsApp button dialled a wrong number until 2026-09-17.
   */
  whatsappE164: "529989370209",
  instagramUrl: "https://www.instagram.com/iguanacomedy/",
  facebookUrl: "https://www.facebook.com/IguanaComedy",
  linkedInUrl: "https://www.linkedin.com/company/iguanacomedy",
  merchantShopUrl: "https://shop.iguanacomedy.com/",
  faviconUrl:
    "/media/favicon.webp",
  heroImage:
    "https://images.unsplash.com/photo-1585699324551-f6c309eedeca?q=80&w=2070&auto=format&fit=crop",
  heroVideoUrl:
    "/media/hero.mp4",
  heroLogoUrl:
    "/media/logo-hero.png",
  brandMomentImage:
    "/media/brand-moment.webp",
  clubPhotoImage:
    "/media/club-photo.webp",
} as const;

export const siteMessages = {
  en: {
    shortTagline:
      "Stand-up comedy club in downtown Playa del Carmen: shows in English and Spanish, plus free open mics on Tuesdays (Spanish) and Wednesdays (English).",
  },
  es: {
    shortTagline:
      "Club de stand-up en el centro de Playa del Carmen: shows en español e inglés y open mic gratis los martes (español) y miércoles (inglés).",
  },
} as const;

/** Hero city labels keyed by slug from ?city= query (optionally aligns with slugify venue city). */
export const heroCityChoices: readonly { slug: string; label: string }[] = [
  { slug: "", label: "the Riviera Maya" },
  { slug: "cancun", label: "Cancún" },
  { slug: "playa-del-carmen", label: "Playa del Carmen" },
  { slug: "tulum", label: "Tulum" },
  { slug: "cozumel", label: "Cozumel" },
  { slug: "puerto-morelos", label: "Puerto Morelos" },
  { slug: "puerto-aventuras", label: "Puerto Aventuras" },
  { slug: "merida", label: "Mérida" },
] as const;

export const experienceStats = [
  {
    value: 100,
    suffix: "+",
    label: { en: "Comedians", es: "Comediantes" },
  },
  {
    value: 50,
    suffix: "+",
    label: { en: "Events", es: "Eventos" },
  },
  {
    value: 5000,
    suffix: "+",
    label: { en: "Attendees", es: "Asistentes" },
  },
] as const;
