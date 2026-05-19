export type Testimonial = {
  quote: Record<"en" | "es", string>;
  author: string;
  city?: string;
  rating: number;
};

export const testimonials: Testimonial[] = [
  {
    rating: 5,
    quote: {
      en: "Honestly the sharpest english comedy night we found in Playa—great pacing, respectful crowd.",
      es: "Sinceramente, la noche de comedia en inglés más afilada que encontramos en Playa: gran ritmo, público respetuoso.",
    },
    author: "Alex M.",
    city: "Playa del Carmen",
  },
  {
    rating: 5,
    quote: {
      en: "We booked seats last minute while on holiday and laughed the entire time. Would go again tonight.",
      es: "Reservamos boletos a último momento de vacaciones y nos reímos todo el tiempo. Volveríamos esta noche.",
    },
    author: "Jordan P.",
    city: "Cancún",
  },
  {
    rating: 5,
    quote: {
      en: "Hosting our small company off-site here was painless—friendly team, smooth ticketing.",
      es: "Organizar nuestro off-site de empresa aquí fue sencillo: equipo amigable, boletería fluida.",
    },
    author: "Laura S.",
    city: "Tulum",
  },
  {
    rating: 5,
    quote: {
      en: "If you assume resort towns can't nail stand-up timing, give this roster a shot. So good.",
      es: "Si crees que los pueblos turísticos no pueden dominar el timing del stand-up, dale una oportunidad a esta cartelera. Excelente.",
    },
    author: "Priya K.",
    city: "Cozumel",
  },
];
