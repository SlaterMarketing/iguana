"use client";

import { useState } from "react";
import type { KintanaClient } from "@kintana/sdk";
import { numberLocale } from "../../lib/kintana-auth";
import type { Locale } from "../../i18n/routes";

function formatDate(iso: string | null, locale: Locale) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(numberLocale(locale), {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function formatCreditNumber(cents: number, locale: Locale) {
  const abs = Math.abs(cents);
  return new Intl.NumberFormat(numberLocale(locale), {
    maximumFractionDigits: abs % 100 === 0 ? 0 : 2,
    minimumFractionDigits: abs % 100 === 0 ? 0 : 2,
  }).format(abs / 100);
}

function formatCredits(cents: number, locale: Locale) {
  return `🎫 ${formatCreditNumber(cents, locale)}`;
}

const copy = {
  en: {
    haveCode: "Have an activation code?",
    placeholder: "Enter code",
    redeem: "Redeem",
    redeeming: "Redeeming…",
    creditsAdded: (added: string, balance: string) =>
      `Added ${added} — balance now ${balance}.`,
    extended: (until: string) => `Membership extended${until ? ` until ${until}` : ""}.`,
    active: (name: string, until: string) =>
      `${name} membership active${until ? ` until ${until}` : ""}.`,
    fail: "Could not redeem that code.",
  },
  es: {
    haveCode: "¿Tienes un código de activación?",
    placeholder: "Ingresa el código",
    redeem: "Canjear",
    redeeming: "Canjeando…",
    creditsAdded: (added: string, balance: string) =>
      `Se agregaron ${added} — saldo actual ${balance}.`,
    extended: (until: string) => `Membresía extendida${until ? ` hasta ${until}` : ""}.`,
    active: (name: string, until: string) =>
      `Membresía ${name} activa${until ? ` hasta ${until}` : ""}.`,
    fail: "No se pudo canjear ese código.",
  },
} as const;

type Props = {
  client: KintanaClient;
  locale: Locale;
  onRedeemed?: () => void | Promise<void>;
  className?: string;
};

export function ActivationCodeRedeemForm({ client, locale, onRedeemed, className }: Props) {
  const t = copy[locale];
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = code.trim();
    if (!trimmed) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const result = await client.redeemFanMembershipCode({ code: trimmed });
      if (result.kind === "credits") {
        setSuccess(
          t.creditsAdded(
            formatCredits(result.amountCents, locale),
            formatCredits(result.newBalanceCents, locale)
          )
        );
      } else {
        const until = formatDate(result.membership.endsAt, locale);
        setSuccess(
          result.extended
            ? t.extended(until)
            : t.active(result.membership.planName, until)
        );
      }
      setCode("");
      await onRedeemed?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.fail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} className={className}>
      <p className="text-sm text-muted">{t.haveCode}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <input
          type="text"
          autoComplete="off"
          spellCheck={false}
          inputMode="text"
          placeholder={t.placeholder}
          className="activation-code-input min-w-[12rem] flex-1 font-mono uppercase tracking-wide"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          disabled={busy}
        />
        <button type="submit" className="btn-outline" disabled={busy || !code.trim()}>
          {busy ? t.redeeming : t.redeem}
        </button>
      </div>
      {success ? <p className="mt-2 text-sm text-brand">{success}</p> : null}
      {error ? <p className="form-error mt-2">{error}</p> : null}
    </form>
  );
}
