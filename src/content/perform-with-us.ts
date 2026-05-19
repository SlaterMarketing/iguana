import { site } from "./site";
import type { Locale } from "../i18n/locale";

export function getPerformPage(locale: Locale) {
  const isES = locale === "es";
  return {
    title: isES ? "Actúa con Iguana" : "Perform with Iguana",
    description: isES
      ? "Comedia en inglés en Cancún, Playa del Carmen, Cozumel, Tulum y más: espacio para headliners de gira y cómicos de vacaciones por igual."
      : "English comedy across Cancún, Playa del Carmen, Cozumel, Tulum, and more—room for touring headliners and vacationing comics alike.",
    intro: isES
      ? [
          "Organizamos comedia en inglés en Cancún, Playa del Carmen, Cozumel, Tulum, Puerto Morelos, Puerto Aventuras y Mérida, trabajando con sedes, hoteles y resorts a lo largo de la costa.",
          "Hay espacio para cómicos de todos los niveles: nombres de la industria de paso, y comediantes de vacaciones que quieren una sala adecuada. A menudo intercambiamos hospedaje y bebidas por sets sólidos cuando el calendario lo permite.",
        ]
      : [
          "We host English-language comedy across Cancún, Playa del Carmen, Cozumel, Tulum, Puerto Morelos, Puerto Aventuras, and Mérida—working with venues, hotels, and resorts along the coast.",
          "There is space for comics at every level: industry names passing through, and comedians on holiday who want a proper room. We often trade accommodation and drinks for strong sets when the calendar allows.",
        ],
    pilgrimageHeading: isES
      ? "Iguana es una peregrinación que todo comediante debe hacer al menos una vez (o más) en la vida."
      : "Iguana is a pilgrimage every comedian has to take once (or more) in a lifetime.",
    pilgrimageBody: isES
      ? "México y el Caribe recompensan a los cómicos que saben leer una multitud mixta: viajeros, locales, personal de hospitalidad y el tío occasional de una boda que cree que pertenece al escenario."
      : "Mexico and the Caribbean reward comics who can read a mixed crowd—travellers, locals, hospitality staff, and the occasional wedding uncle who thinks he belongs on stage.",
    offersHeading: isES ? "Lo que ofrecemos" : "What we can offer",
    formHeading: isES ? "Actúa con Iguana" : "Perform with Iguana",
    formIntro: isES
      ? "Cuéntanos de dónde eres, qué tienes en video y cuándo podrías llegar. Respondemos desde el equipo de producción, no un bot."
      : "Tell us where you are based, what you have on tape, and when you could land. We reply from the producing desk—not a bot.",
    galleryImages: [
      site.clubPhotoImage,
      site.brandMomentImage,
      "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/fc28c62ff25bfe59ab4a1b77d48f063eeba57ba8c4f7605211cfd701fa7c6d27.jpg",
    ],
    formBackdrop:
      "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/e3861e77e1377e8c41284752355ab7b3b815031fcb684553d4ecb115c3e792ed.jpg",
  } as const;
}

export function getPerformOffers(locale: Locale) {
  const isES = locale === "es";
  return [
    { title: isES ? "Conoce nuevos comediantes" : "Meet new comedians" },
    { title: isES ? "Oficialmente conviértete en comediante internacional" : "Officially become an international comedian" },
    { title: isES ? "Experimenta la cultura mexicana" : "Experience Mexican culture" },
    { title: isES ? "Hospedaje gratuito en Cancún y Playa" : "Free accommodation in Cancún and Playa" },
    { title: isES ? "Únete a nuestro muro de comediantes" : "Join our wall of comedians", highlight: true },
    { title: isES ? "Material de video de alta calidad, editado y crudo" : "High quality, edited and raw footage" },
  ] as const;
}

export function getPerformFaq(locale: Locale) {
  const isES = locale === "es";
  return [
    {
      question: isES ? "¿Cómo es actuar con Iguana?" : "What is performing with Iguana like?",
      answer: isES
        ? "Las salas son bilingües-friendly, los tiempos se respetan, y los hosts saben cómo calentar una multitud de viajeros sin hablarles por encima. Recibes un check-in adecuado, un stage plot claro, y productores que han hecho el trabajo antes de abrir puertas."
        : "Rooms are bilingual-friendly, run times are respected, and hosts know how to warm a travel crowd without talking down to them. You get a proper check-in, a clear stage plot, and producers who have done the work before doors open.",
      open: true,
    },
    {
      question: isES ? "¿Cómo funciona?" : "How does it work?",
      answer: isES
        ? "Envía tu reel, ventana de pasaporte y cualquier nota sobre hotel o dieta. Te colocamos en showcases, open mics o features de una noche según las necesidades de la cartelera. Si ya estás en la ciudad, dinos: a menudo nos movemos más rápido de lo que esperas."
        : "Send your reel, passport window, and any hotel or dietary notes. We slot you into showcases, open mics, or one-off features depending on lineup needs. If you are already in town, say so—we often move faster than you expect.",
    },
    {
      question: isES ? "¿Se paga?" : "Will I get paid?",
      answer: isES
        ? "Las semanas de headline y feature son pagadas cuando el calendario se construye de esa forma. Muchos intercambios de vacación intercambian un guest set ajustado por hospedaje y hospitalidad: somos claros sobre en qué bucket estás antes de que compres vuelos."
        : "Headline and feature weeks are paid when the calendar is built that way. Many vacation swaps trade a tight guest set for accommodation and hospitality—we are upfront about which bucket you are in before you book flights.",
    },
  ] as const;
}
