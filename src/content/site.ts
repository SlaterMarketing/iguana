/**
 * Editorial copy & brand contacts — tweak here without chasing UI internals.
 */

export const site = {
  name: "Iguana Comedy",
  shortTagline: "English stand-up comedy across Cancún, Playa, Tulum, Cozumel, and more.",
  email: "hello@iguanacomedy.com",
  /** Full international display (WhatsApp widget text) */
  whatsappDisplay: "+52 998 937 0209",
  /** Numeric only — used in wa.me links */
  whatsappE164: "529889370209",
  instagramUrl: "https://www.instagram.com/iguanacomedy/",
  facebookUrl: "https://www.facebook.com/IguanaComedy",
  linkedInUrl: "https://www.linkedin.com/company/iguanacomedy",
  merchantShopUrl: "https://shop.iguanacomedy.com/",
  heroImage:
    "https://images.unsplash.com/photo-1585699324551-f6c309eedeca?q=80&w=2070&auto=format&fit=crop",
  heroVideoUrl:
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/b95b1066ef9a5f4c5ea44b24556fbaa917690ed4a46d196689804705ed7e4fdf.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=67dc011dab30cb610adb962a4a211efd%2F20260518%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20260518T215704Z&X-Amz-Expires=3600&X-Amz-Signature=3148170ad962e3a72fa74c1f584d485216386655eea9a6eb4361a41234fa51e9&X-Amz-SignedHeaders=host&x-id=GetObject",
  heroLogoUrl:
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/72bc27068af9b73439a6954aed55729ec8803ddd8f32c6a07b9181b597580f1e.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=67dc011dab30cb610adb962a4a211efd%2F20260518%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20260518T221118Z&X-Amz-Expires=3600&X-Amz-Signature=22c181a18f9c13cd4012f124365a650f3cefb0c02defe5c4dc93938f70b67b72&X-Amz-SignedHeaders=host&x-id=GetObject",
  brandMomentImage:
    "https://images.unsplash.com/photo-1506953823976-52e1fdc0149a?q=80&w=1200&auto=format&fit=crop",
  clubPhotoImage:
    "https://images.unsplash.com/photo-1540039155733-5bb546b929d3?q=80&w=1200&auto=format&fit=crop",
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
    label: "Comedians",
  },
  {
    value: 50,
    suffix: "+",
    label: "Events",
  },
  {
    value: 5000,
    suffix: "+",
    label: "Attendees",
  },
] as const;
