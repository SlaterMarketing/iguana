/**
 * The bar menu, and sending a round from a table.
 *
 * The menu is served by the Django backend rather than written into this repo, because a price changes on the
 * night it changes and a deploy is the wrong thing to need at 9pm.
 */

export type MenuItem = { id: string; name: string; description: string; priceCents: number; currency: string };
export type MenuCategory = { id: string; name: string; items: MenuItem[] };
export type Menu = { maxTable: number; categories: MenuCategory[] };

/** The last table in the room. The QRs are printed once, so this is fixed here and in `api/menu_views.py`. */
export const MAX_TABLE = 100;

export function isTableNumber(value: string | undefined): boolean {
  if (!value) return false;
  if (!/^[0-9]{1,3}$/.test(value)) return false;
  const n = Number(value);
  return n >= 1 && n <= MAX_TABLE;
}

export function formatMenuPrice(item: Pick<MenuItem, "priceCents" | "currency">, locale: "en" | "es"): string {
  const amount = new Intl.NumberFormat(locale === "es" ? "es-MX" : "en-US", {
    minimumFractionDigits: item.priceCents % 100 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(item.priceCents / 100);
  return `$${amount} ${item.currency}`;
}

export async function loadMenu(baseUrl: string, apiKey: string, locale: "en" | "es"): Promise<Menu | null> {
  try {
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/public/v1/menu?locale=${locale}`, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (!response.ok) return null;
    return (await response.json()) as Menu;
  } catch {
    return null;
  }
}
