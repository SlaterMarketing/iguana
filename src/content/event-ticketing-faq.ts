import type { Locale } from "../i18n/locale";

type FaqItem = { question: string; answer: string; open?: boolean };

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
        "Refunds follow the policy shown at checkout and in your confirmation email. Contact us before the show if your plans change—we will help when we can.",
    },
    {
      question: "Is there an age limit?",
      answer:
        "Most nights are 18+ unless the listing says otherwise. Bring valid ID if the venue asks for it at the door.",
    },
    {
      question: "Where is the venue?",
      answer:
        "Each show lists the room and address on this page. Tap View on Google Maps for directions.",
    },
    {
      question: "What time do doors open?",
      answer:
        "Doors and show times are listed on your ticket and at the top of this page. We recommend arriving early for the best seats.",
    },
    {
      question: "Is the venue accessible?",
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
        "Los reembolsos siguen la política mostrada en el checkout y en tu correo de confirmación. Escríbenos antes del show si cambian tus planes—te ayudaremos cuando podamos.",
    },
    {
      question: "¿Hay límite de edad?",
      answer:
        "La mayoría de las noches son 18+ salvo que el listing indique lo contrario. Lleva identificación válida si el venue la solicita en la puerta.",
    },
    {
      question: "¿Dónde está el venue?",
      answer:
        "Cada show lista el room y la dirección en esta página. Toca Ver en Google Maps para indicaciones.",
    },
    {
      question: "¿A qué hora abren las puertas?",
      answer:
        "Puertas y horario del show aparecen en tu boleto y arriba en esta página. Recomendamos llegar temprano para mejores asientos.",
    },
    {
      question: "¿El venue es accesible?",
      answer:
        "Contáctanos antes de comprar si necesitas acceso sin escaleras u otras adaptaciones—confirmaremos lo posible para ese room.",
    },
  ],
};

export function getEventTicketingFaq(locale: Locale): FaqItem[] {
  return FAQ[locale];
}
