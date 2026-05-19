import { site } from "./site";
import type { Locale } from "../i18n/locale";

export function getHotelsPage(locale: Locale) {
  const isES = locale === "es";
  return {
    title: isES
      ? "Shows para hoteles y resorts"
      : "Shows for hotels and resorts",
    description: isES
      ? "Programación de comedia en inglés para hoteles y resorts en Quintana Roo: noches a la medida, alianzas a largo plazo y producción que tus gerentes de entretenimiento pueden confiar."
      : "English stand-up programming for hotels and resorts across Quintana Roo—bespoke nights, long-term partnerships, and producing your entertainment managers can trust.",
    intro: isES
      ? [
          "Nuestros shows para hoteles y resorts son acuerdos de entretenimiento a la medida y a largo plazo en múltiples ciudades de Quintana Roo. Trabajamos con tu equipo de programación para ajustar el tono, la capacidad y el run-of-show, ya sea un showcase único o un slot recurrente en el calendario.",
          "Somos el único proveedor dedicado de comedia en inglés de alta calidad en la región. Eso significa comediantes que saben leer a una multitud de viajeros, hosts que mantienen las intros bilingües ágiles, y un equipo de producción que responde antes de que tus gerentes de noche estén persiguiendo sound checks.",
        ]
      : [
          "Our shows for hotels and resorts are bespoke and long-term entertainment agreements across multiple cities in Quintana Roo. We work with your programming team to match tone, capacity, and run-of-show—whether that is a one-off showcase or a recurring slot in the calendar.",
          "We are the only dedicated provider of high-quality English stand-up comedy in the region. That means comics who can read a travel crowd, hosts who keep bilingual intros tight, and a producing desk that answers before your night managers are chasing sound checks.",
        ],
    credibilityHeading: isES
      ? "Iguana ha trabajado con muchos hoteles y resorts a lo largo de los años para ofrecer comedia stand-up de primer nivel."
      : "Iguana has worked with many hotels and resorts over the years to provide top tier stand up comedy.",
    credibilityBody: isES
      ? "Desde salones de lobby hasta showcases en salones de eventos, traemos carteleras repetibles, flujos claros de boletos o cortesías cuando los necesitas, y material de video que puedes usar para marketing, sin improvisar hojas de cálculo la noche antes de abrir puertas."
      : "From lobby lounges to ballroom showcases, we bring repeatable lineups, clear ticketing or comp flows when you need them, and footage you can use for marketing—without improvising spreadsheets the night before doors.",
    offersHeading: isES ? "Lo que ofrecemos" : "What we can offer",
    formHeading: isES
      ? "Cuéntanos sobre las necesidades de tu hotel/resort"
      : "Tell us about your hotel/resort needs",
    formIntro: isES
      ? "Comparte detalles de la propiedad, fechas preferidas, mix de audiencia y cualquier restricción de AV o F&B. Respondemos desde el equipo de producción con disponibilidad y opciones, no un brochure genérico."
      : "Share property details, preferred dates, audience mix, and any AV or F&B constraints. We reply from the producing desk with availability and options—not a generic brochure.",
    galleryImages: [
      site.clubPhotoImage,
      "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/fc28c62ff25bfe59ab4a1b77d48f063eeba57ba8c4f7605211cfd701fa7c6d27.jpg",
      site.brandMomentImage,
    ],
    formBackdrop:
      "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/e3861e77e1377e8c41284752355ab7b3b815031fcb684553d4ecb115c3e792ed.jpg",
  } as const;
}

export function getHospitalityStats(locale: Locale) {
  const isES = locale === "es";
  return [
    { value: 20, suffix: "+", label: isES ? "Hoteles" : "Hotels" },
    { value: 27, suffix: "+", label: isES ? "Shows" : "Shows" },
    { value: 10000, suffix: "+", label: isES ? "Audiencia" : "Audience" },
  ] as const;
}

export function getHotelsOffers(locale: Locale) {
  const isES = locale === "es";
  return [
    { title: isES ? "Comediantes para eventos específicos" : "Comedians for specific events" },
    { title: isES ? "Estilo y temas específicos" : "Specific styling and topics" },
    { title: isES ? "Alianzas a largo plazo" : "Long term partnerships" },
    { title: isES ? "Hosting y presentación" : "Hosting and presenting" },
    { title: isES ? "Material de video de alta calidad" : "High quality footage" },
    { title: isES ? "Una experiencia sin igual" : "An unmatched experience", highlight: true },
  ] as const;
}

export function getHotelsFaq(locale: Locale) {
  const isES = locale === "es";
  return [
    {
      question: isES ? "¿Cuál es su disponibilidad?" : "What's your availability?",
      answer: isES
        ? "Programamos todo el año en Cancún, Playa del Carmen, Tulum, Cozumel, Puerto Morelos, Puerto Aventuras y Mérida. Envía tu ventana y tipo de sala: responderemos con fechas que encajen en tu calendario de entretenimiento, no solo con lo que quede en una hoja de gira genérica."
        : "We programme year-round across Cancún, Playa del Carmen, Tulum, Cozumel, Puerto Morelos, Puerto Aventuras, and Mérida. Send your window and room type—we will come back with dates that fit your entertainment calendar, not just whatever is left on a generic tour sheet.",
      open: true,
    },
    {
      question: isES ? "¿Qué tipo de comedia pueden ofrecer?" : "What kind of comedy can you provide?",
      answer: isES
        ? "Showcases limpios para multitudes mixtas de resort, slots más atrevidos para noches tardías cuando la sala lo permite, hosting y presentación para galas, y noches temáticas cuando necesitas un ángulo específico. Cada cómico recibe un briefing sobre tu propiedad y audiencia antes de llegar."
        : "Clean showcases for mixed resort crowds, edgier late slots when the room allows, hosting and presenting for galas, and themed nights when you need a specific angle. Every comic is briefed on your property and audience before they land.",
    },
    {
      question: isES ? "¿Cuánto cuestan?" : "How much do you cost?",
      answer: isES
        ? "El precio depende de la profundidad de la cartelera, viaje, tecnología y si quieres una sola noche o un paquete de temporada. Cotizamos claramente desde el inicio para que tu GM y equipos de F&B no tengan sorpresas después."
        : "Pricing depends on lineup depth, travel, tech, and whether you want a single night or a season package. We quote clearly up front so your GM and F&B leads are not surprised after the fact.",
    },
    {
      question: isES ? "¿Cómo se realiza el pago?" : "How do you take payment?",
      answer: isES
        ? "Facturamos en MXN o USD con términos estándar de hospitalidad. Para shows públicos con boletería podemos manejar flujos de cortesía y pagados desde nuestro equipo; para noches privadas de resort nos alineamos con tu proceso de cuentas por pagar."
        : "We invoice in MXN or USD with standard hospitality terms. For ticketed public shows we can run comp and paid flows through our desk; for private resort nights we align with your AP process.",
    },
  ] as const;
}
