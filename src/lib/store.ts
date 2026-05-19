/** Format store prices from Kintana `*Cents` fields. */
export function formatStorePrice(cents: number | null | undefined, currency = "USD"): string | null {
  if (cents == null || !Number.isFinite(cents)) return null;
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency.toUpperCase(),
      maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
    }).format(cents / 100);
  } catch {
    return `$${(cents / 100).toFixed(2)}`;
  }
}

export function storePriceLabel(
  priceFromCents: number | null,
  compareAtCents: number | null | undefined,
  currency: string,
): string {
  const price = formatStorePrice(priceFromCents, currency);
  const compare = compareAtCents != null ? formatStorePrice(compareAtCents, currency) : null;
  if (!price) return "Price at checkout";
  if (compare && compareAtCents != null && priceFromCents != null && compareAtCents > priceFromCents) {
    return `${price} · was ${compare}`;
  }
  return price;
}
