/** Press lines shown on event detail pages (matches Kintana ticketing layout). */
export const pressQuotes: ReadonlyArray<{ quote: string; stars: number; source: string }> = [
  { quote: "Leaves them howling with laughter.", stars: 5, source: "Sunday Express" },
  { quote: "Combination of quirkiness and intelligence. A pleasure.", stars: 4, source: "The Telegraph" },
  { quote: "A winning presence from the first word to the last.", stars: 5, source: "The Recs" },
  { quote: "Hugely entertaining storytelling.", stars: 5, source: "Three Weeks" },
  { quote: "Gut-bustlingly funny.", stars: 5, source: "Mumble" },
  { quote: "Brilliantly funny; a firecracker of a performer.", stars: 4, source: "Broadway Baby" },
  { quote: "", stars: 4, source: "Ed Fest" },
  { quote: "", stars: 4, source: "Entertainment Now" },
];

export function formatStarRating(stars: number): string {
  return "★".repeat(Math.max(0, Math.min(5, stars)));
}
