import type { KintanaPublicEvent } from "@kintana/sdk";
import { formatEventTime } from "../lib/events";
import { eventVenueLabel } from "../lib/event-hero";
import type { Locale } from "../i18n/locale";

type FaqItem = { question: string; answer: string; open?: boolean };

const ACCESSIBILITY_QUESTION: Record<Locale, string> = {
  en: "Is the venue accessible?",
  es: "¿El venue es accesible?",
};

const DOORS_QUESTION: Record<Locale, string> = {
  en: "What time do doors open?",
  es: "¿A qué hora abren las puertas?",
};

const VENUE_QUESTION: Record<Locale, string> = {
  en: "Where is the venue?",
  es: "¿Dónde está el venue?",
};

const FAQ: Record<Locale, FaqItem[]> = {
  en: [
    {
      question: "How do I get my tickets?",
      answer:
        "After checkout you receive a confirmation email with your tickets. You can also view them from the order link on the confirmation screen.",
      open: true,
    },
    {
      question: "What is the refund policy?",
      answer:
        "We honour refunds when you request them more than 48 hours before the show. Contact us if your plans change—we will help when we can.",
    },
    {
      question: "Is there an age limit?",
      answer:
        "Teenagers 16 and up are welcome. Our comedians may discuss adult topics, and they won't change their material because teens are in the audience.",
    },
    {
      question: VENUE_QUESTION.en,
      answer:
        "Each show lists the room and address on this page. Tap View on Google Maps for directions.",
    },
    {
      question: DOORS_QUESTION.en,
      answer:
        "Doors and show times are listed on your ticket and at the top of this page. We recommend arriving early for the best seats.",
    },
    {
      question: ACCESSIBILITY_QUESTION.en,
      answer:
        "Contact us before you buy if you need step-free access or other accommodations—we will confirm what is possible for that room.",
    },
  ],
  es: [
    {
      question: "¿Cómo recibo mis boletos?",
      answer:
        "Después del checkout recibes un correo de confirmación con tus boletos. También puedes verlos desde el enlace de la orden en la pantalla de confirmación.",
      open: true,
    },
    {
      question: "¿Cuál es la política de reembolso?",
      answer:
        "Honramos reembolsos cuando los solicitas con más de 48 horas de anticipación al show. Escríbenos si cambian tus planes—te ayudaremos cuando podamos.",
    },
    {
      question: "¿Hay límite de edad?",
      answer:
        "Adolescentes de 16 años en adelante son bienvenidos. Nuestros comediantes pueden hablar de temas para adultos y no modificarán su material por la presencia de adolescentes en el público.",
    },
    {
      question: VENUE_QUESTION.es,
      answer:
        "Cada show lista el room y la dirección en esta página. Toca Ver en Google Maps para indicaciones.",
    },
    {
      question: DOORS_QUESTION.es,
      answer:
        "Puertas y horario del show aparecen en tu boleto y arriba en esta página. Recomendamos llegar temprano para mejores asientos.",
    },
    {
      question: ACCESSIBILITY_QUESTION.es,
      answer:
        "Contáctanos antes de comprar si necesitas acceso sin escaleras u otras adaptaciones—confirmaremos lo posible para ese room.",
    },
  ],
};

function venueFaqAnswer(
  locale: Locale,
  event: Pick<KintanaPublicEvent, "venue" | "city" | "country">
): string | null {
  const venueName = event.venue?.name?.trim() || eventVenueLabel(event);
  const address = event.venue?.address?.trim();
  if (!venueName && !address) return null;

  if (locale === "es") {
    if (venueName && address) {
      return `${venueName} está en ${address}. Toca Ver en Google Maps arriba para indicaciones.`;
    }
    if (venueName) {
      return `${venueName}. Toca Ver en Google Maps en la sección del venue arriba para indicaciones.`;
    }
    return `${address}. Toca Ver en Google Maps arriba para indicaciones.`;
  }

  if (venueName && address) {
    return `${venueName} is at ${address}. Tap View on Google Maps above for directions.`;
  }
  if (venueName) {
    return `${venueName}. Tap View on Google Maps in the venue section above for directions.`;
  }
  return `${address}. Tap View on Google Maps above for directions.`;
}

function doorsFaqAnswer(
  locale: Locale,
  event: Pick<KintanaPublicEvent, "doorsOpen" | "showTime">
): string | null {
  const doors = formatEventTime(event.doorsOpen, locale);
  const show = formatEventTime(event.showTime, locale);
  if (!doors && !show) return null;

  if (locale === "es") {
    if (doors && show) {
      return `Las puertas abren a las ${doors} y el show empieza a las ${show}. Recomendamos llegar temprano para mejores asientos.`;
    }
    if (doors) {
      return `Las puertas abren a las ${doors}. Recomendamos llegar temprano para mejores asientos.`;
    }
    return `El show empieza a las ${show}. Recomendamos llegar temprano para mejores asientos.`;
  }

  if (doors && show) {
    return `Doors open at ${doors} and the show starts at ${show}. We recommend arriving early for the best seats.`;
  }
  if (doors) {
    return `Doors open at ${doors}. We recommend arriving early for the best seats.`;
  }
  return `The show starts at ${show}. We recommend arriving early for the best seats.`;
}

function accessibilityFaqAnswer(
  locale: Locale,
  venueName: string,
  wheelchairAccessible: boolean
): string {
  if (wheelchairAccessible) {
    return locale === "es"
      ? `${venueName} está marcado como accesible para sillas de ruedas. Escríbenos antes de comprar si necesitas algo más específico.`
      : `${venueName} is marked as wheelchair accessible. Contact us before you buy if you need anything more specific.`;
  }
  return locale === "es"
    ? `${venueName} no está marcado como accesible con silla de ruedas. Contáctanos antes de comprar si necesitas acceso sin escaleras u otras adaptaciones—confirmaremos lo posible.`
    : `${venueName} is not marked as wheelchair accessible. Contact us before you buy if you need step-free access or other accommodations—we will confirm what is possible for that room.`;
}

export function getEventTicketingFaq(
  locale: Locale,
  event?: Pick<KintanaPublicEvent, "doorsOpen" | "showTime" | "venue" | "city" | "country"> | null
): FaqItem[] {
  const items = FAQ[locale].map((item) => ({ ...item }));
  if (!event) return items;

  const venueIndex = items.findIndex((item) => item.question === VENUE_QUESTION[locale]);
  const venueAnswer = venueFaqAnswer(locale, event);
  if (venueIndex !== -1 && venueAnswer) {
    items[venueIndex] = { ...items[venueIndex], answer: venueAnswer };
  }

  const doorsIndex = items.findIndex((item) => item.question === DOORS_QUESTION[locale]);
  const doorsAnswer = doorsFaqAnswer(locale, event);
  if (doorsIndex !== -1 && doorsAnswer) {
    items[doorsIndex] = { ...items[doorsIndex], answer: doorsAnswer };
  }

  const wheelchairAccessible = event.venue?.wheelchairAccessible;
  if (wheelchairAccessible != null) {
    const venueName = event.venue?.name?.trim() || (locale === "es" ? "Este venue" : "This venue");
    const accessibilityIndex = items.findIndex((item) => item.question === ACCESSIBILITY_QUESTION[locale]);
    if (accessibilityIndex !== -1) {
      items[accessibilityIndex] = {
        ...items[accessibilityIndex],
        answer: accessibilityFaqAnswer(locale, venueName, wheelchairAccessible),
      };
    }
  }

  return items;
}
