/**
 * Editorial copy & brand contacts — tweak here without chasing UI internals.
 */

export const site = {
  name: "Iguana Comedy",
  email: "hello@iguanacomedy.com",
  /** Full international display (WhatsApp widget text) */
  whatsappDisplay: "+52 998 937 0209",
  /** Numeric only — used in wa.me links */
  whatsappE164: "529889370209",
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
      "English stand-up comedy across Cancún, Playa, Tulum, Cozumel, and more.",
  },
  es: {
    shortTagline:
      "Comedia en inglés en Cancún, Playa, Tulum, Cozumel y más.",
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
