import type { KintanaPublicEvent, KintanaPublicEventReview } from "@kintana/sdk";

export function eventReviews(event: Pick<KintanaPublicEvent, "reviews">): KintanaPublicEventReview[] {
  return event.reviews?.filter((item) => item.source.trim()) ?? [];
}

export function formatStarRating(stars: number): string {
  return "★".repeat(Math.max(0, Math.min(5, stars)));
}
