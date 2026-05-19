export type Testimonial = {
  quote: string;
  author: string;
  city?: string;
  rating: number;
};

export const testimonials: Testimonial[] = [
  {
    rating: 5,
    quote:
      "Honestly the sharpest english comedy night we found in Playa—great pacing, respectful crowd.",
    author: "Alex M.",
    city: "Playa del Carmen",
  },
  {
    rating: 5,
    quote:
      "We booked seats last minute while on holiday and laughed the entire time. Would go again tonight.",
    author: "Jordan P.",
    city: "Cancún",
  },
  {
    rating: 5,
    quote: "Hosting our small company off-site here was painless—friendly team, smooth ticketing.",
    author: "Laura S.",
    city: "Tulum",
  },
  {
    rating: 5,
    quote:
      "If you assume resort towns can’t nail stand-up timing, give this roster a shot. So good.",
    author: "Priya K.",
    city: "Cozumel",
  },
];
