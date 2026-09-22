import { useMemo, useState } from "react";

import type { Locale } from "../../i18n/locale";
import { formatMenuPrice, MAX_TABLE, type Menu } from "../../lib/menu";

/**
 * Order a round from the table.
 *
 * The whole point is that nobody stands up during a set. So: tap the pluses, send, and the bar gets the table
 * number with the round. No card, no account, no email address. Payment stays at the table where it already is,
 * which also means this can never take money and fail to deliver a drink.
 */

const copy = {
  en: {
    at: (table: number) => `Table ${table}`,
    whichTable: "Which table are you at?",
    tablePlaceholder: "Table number",
    needTable: "Put your table number in so we know where to bring it.",
    note: "Anything we should know?",
    notePlaceholder: "No ice, extra lime…",
    send: (total: string) => `Send to the bar · ${total}`,
    sending: "Sending…",
    empty: "Tap + on anything you want",
    payAtTable: "You pay at the table at the end of the night, all together.",
    houseRules: "Phones on silent please, and no recording during the show.",
    failed: "That did not send. Try again, or wave at the bar.",
    again: "Order something else",
    sentFallback: "Order sent to the bar.",
  },
  es: {
    at: (table: number) => `Mesa ${table}`,
    whichTable: "¿En qué mesa estás?",
    tablePlaceholder: "Número de mesa",
    needTable: "Pon tu número de mesa para saber a dónde llevarlo.",
    note: "¿Algo que debamos saber?",
    notePlaceholder: "Sin hielo, con limón de más…",
    send: (total: string) => `Enviar a la barra · ${total}`,
    sending: "Enviando…",
    empty: "Toca + en lo que quieras",
    payAtTable: "Pagas en la mesa al final de la noche, todo junto.",
    houseRules: "Pon el celular en silencio, por favor, y no grabes durante el show.",
    failed: "No se envió. Inténtalo otra vez o haz una señal en la barra.",
    again: "Pedir algo más",
    sentFallback: "Pedido enviado a la barra.",
  },
} as const;

type Props = { locale: Locale; table?: number; menu: Menu; baseUrl: string; apiKey: string };

/**
 * `table` comes from the URL when the code was stuck to one table. Without it the customer types the number,
 * which is why a single printed code can serve the whole room: one poster instead of a hundred stickers, and
 * nothing to reprint when the furniture moves.
 */
export function TableOrderIsland({ locale, table: fixedTable, menu, baseUrl, apiKey }: Props) {
  const t = copy[locale];
  const [typedTable, setTypedTable] = useState("");
  const table = fixedTable ?? (/^[0-9]{1,3}$/.test(typedTable) ? Number(typedTable) : 0);
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState("");

  const items = useMemo(() => menu.categories.flatMap((category) => category.items), [menu]);
  const currency = items[0]?.currency ?? "MXN";
  const totalCents = items.reduce((sum, item) => sum + item.priceCents * (quantities[item.id] ?? 0), 0);
  const chosen = Object.values(quantities).reduce((a, b) => a + b, 0);
  const total = formatMenuPrice({ priceCents: totalCents, currency }, locale);

  function bump(id: string, by: number) {
    setError("");
    setQuantities((current) => {
      const next = Math.min(20, Math.max(0, (current[id] ?? 0) + by));
      const copied = { ...current };
      if (next === 0) delete copied[id];
      else copied[id] = next;
      return copied;
    });
  }

  async function send() {
    if (!chosen || busy) return;
    if (!table || table < 1 || table > MAX_TABLE) {
      setError(t.needTable);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/public/v1/table-orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
        body: JSON.stringify({ table, items: quantities, note, lang: locale }),
      });
      const body = (await response.json().catch(() => ({}))) as { error?: string; message?: string };
      if (!response.ok) throw new Error(body.error || t.failed);
      setSent(body.message || t.sentFallback);
      setQuantities({});
      setNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t.failed);
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="rounded-3xl border border-brand/40 bg-brand/10 px-6 py-8 text-center">
        <p className="text-lg font-semibold text-neutral-950">{sent}</p>
        <p className="mt-2 text-sm text-neutral-700">{t.payAtTable}</p>
        <p className="mt-1 text-sm text-neutral-700">{t.houseRules}</p>
        <button
          type="button"
          className="mt-6 rounded-full bg-neutral-950 px-8 py-3 text-xs font-semibold uppercase tracking-[0.3em] text-white"
          onClick={() => setSent("")}
        >
          {t.again}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {menu.categories.map((category) => (
        <section key={category.id} className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-[0.42em] text-neutral-500">{category.name}</h2>
          <ul className="divide-y divide-black/10 border-y border-black/10">
            {category.items.map((item) => (
              <li key={item.id} className="flex items-center gap-4 py-3 text-left">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-neutral-950">{item.name}</p>
                  {item.description ? <p className="text-sm text-neutral-600">{item.description}</p> : null}
                  <p className="text-sm text-neutral-700">{formatMenuPrice(item, locale)}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    aria-label={`-1 ${item.name}`}
                    className="size-11 rounded-full border border-black/25 text-xl leading-none text-neutral-950 disabled:opacity-30"
                    disabled={!quantities[item.id]}
                    onClick={() => bump(item.id, -1)}
                  >
                    −
                  </button>
                  <output className="min-w-[2ch] text-center text-lg font-bold tabular-nums">{quantities[item.id] ?? 0}</output>
                  <button
                    type="button"
                    aria-label={`+1 ${item.name}`}
                    className="size-11 rounded-full bg-neutral-950 text-xl leading-none text-white"
                    onClick={() => bump(item.id, 1)}
                  >
                    +
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {fixedTable ? null : (
        <label className="block text-left">
          <span className="text-xs font-semibold uppercase tracking-[0.3em] text-neutral-500">{t.whichTable}</span>
          <input
            className="mt-2 min-h-12 w-full rounded-2xl border border-black/20 px-4 text-lg font-semibold"
            value={typedTable}
            inputMode="numeric"
            autoComplete="off"
            maxLength={3}
            placeholder={t.tablePlaceholder}
            onChange={(event) => {
              setError("");
              setTypedTable(event.target.value.replace(/[^0-9]/g, "").slice(0, 3));
            }}
          />
        </label>
      )}

      <label className="block text-left">
        <span className="text-xs font-semibold uppercase tracking-[0.3em] text-neutral-500">{t.note}</span>
        <input
          className="mt-2 min-h-12 w-full rounded-2xl border border-black/20 px-4 text-base"
          value={note}
          maxLength={300}
          placeholder={t.notePlaceholder}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>

      <p className="rounded-2xl bg-neutral-100 px-4 py-3 text-sm text-neutral-700">
        {t.payAtTable} {t.houseRules}
      </p>

      {error ? <p className="text-sm font-semibold text-red-700">{error}</p> : null}

      {/* Sticky, because the list is longer than a phone and the whole idea is one tap from anywhere in it. */}
      <div className="sticky bottom-3 z-10">
        <button
          type="button"
          className="flex min-h-14 w-full items-center justify-center rounded-full bg-brand px-8 text-sm font-semibold uppercase tracking-[0.2em] text-neutral-950 shadow-lg shadow-black/20 disabled:opacity-60"
          disabled={!chosen || busy}
          onClick={send}
        >
          {busy ? t.sending : chosen ? t.send(total) : t.empty}
        </button>
        {table ? <p className="mt-2 text-center text-xs text-neutral-600">{t.at(table)}</p> : null}
      </div>
    </div>
  );
}
