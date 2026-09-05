"use client";

import { useEffect, useState } from "react";
import type {
  KintanaFanAccountProfile,
  KintanaFanCreditTransfer,
  KintanaFanMembershipStatus,
  KintanaFanTicket,
} from "@kintana/sdk";
import { KintanaAuthProvider, useKintanaAuth } from "@kintana/sdk/react";
import { ActivationCodeRedeemForm } from "../membership/ActivationCodeRedeemForm";
import {
  accountReturnUrl,
  membershipPaths,
  numberLocale,
  signInUrlWithNext,
} from "../../lib/kintana-auth";
import type { Locale } from "../../i18n/routes";

export type AccountView = "membership" | "tickets" | "profile";

type Props = {
  apiKey: string;
  baseUrl: string;
  locale: Locale;
  view: AccountView;
};

const copy = {
  en: {
    nav: { membership: "Membership", tickets: "Tickets", profile: "Profile" },
    titles: { membership: "Membership", tickets: "Tickets", profile: "Profile" },
    loadingAccount: "Loading your account…",
    loadAccountFail: "Could not load your account.",
    signOut: "Sign out",
    flashJoined: "You’re in — your membership is active.",
    loadingMembership: "Loading membership…",
    loadMembershipFail: "Could not load your membership.",
    notMember: "You’re not a member yet.",
    joinNow: "Join now",
    manageBilling: "Manage billing",
    opening: "Opening…",
    billingUnavailable: "Billing is not available for your membership.",
    creditsTitle: "Iguana credits",
    creditsNote: "Credits stay with Iguana Comedy and can be used on tickets.",
    creditsPending: (amount: string) =>
      `You have ${amount} in credits waiting — join to unlock them.`,
    creditsPendingLand: (amount: string) => `${amount} still waiting to land on your membership.`,
    sendTo: "Send to",
    amount: "Amount",
    sendCredits: "Send credits",
    sending: "Sending…",
    noCredits: "No credits to send yet.",
    enterAmount: "Enter an amount to send.",
    tooMuch: "That’s more than your credit balance.",
    sentPending: (email: string) => `Sent — waiting for ${email} to join.`,
    sentOk: (amount: string, email: string) => `Sent ${amount} to ${email}.`,
    sendFail: "Could not send credits.",
    sentTo: "Sent to",
    from: "From",
    waitingJoin: "Waiting for them to join",
    loadingTickets: "Loading tickets…",
    loadTicketsFail: "Could not load your tickets.",
    noTickets: "No ticket orders yet.",
    whatsOn: "What’s on",
    ticketCount: (n: number) => `${n} ticket${n === 1 ? "" : "s"}`,
    viewTickets: "View tickets",
    firstName: "First name",
    lastName: "Last name",
    phone: "Phone",
    saved: "Saved",
    saveFail: "Could not save. Try again.",
    saveProfile: "Save profile",
    saving: "Saving…",
    fromDate: "from",
    until: "until",
  },
  es: {
    nav: { membership: "Membresía", tickets: "Boletos", profile: "Perfil" },
    titles: { membership: "Membresía", tickets: "Boletos", profile: "Perfil" },
    loadingAccount: "Cargando tu cuenta…",
    loadAccountFail: "No se pudo cargar tu cuenta.",
    signOut: "Cerrar sesión",
    flashJoined: "Listo — tu membresía está activa.",
    loadingMembership: "Cargando membresía…",
    loadMembershipFail: "No se pudo cargar tu membresía.",
    notMember: "Aún no eres miembro.",
    joinNow: "Únete ahora",
    manageBilling: "Administrar facturación",
    opening: "Abriendo…",
    billingUnavailable: "La facturación no está disponible para tu membresía.",
    creditsTitle: "Créditos Iguana",
    creditsNote: "Los créditos se quedan en Iguana Comedy y se pueden usar en boletos.",
    creditsPending: (amount: string) =>
      `Tienes ${amount} en créditos en espera — únete para desbloquearlos.`,
    creditsPendingLand: (amount: string) =>
      `${amount} aún esperando llegar a tu membresía.`,
    sendTo: "Enviar a",
    amount: "Monto",
    sendCredits: "Enviar créditos",
    sending: "Enviando…",
    noCredits: "Aún no hay créditos para enviar.",
    enterAmount: "Ingresa un monto a enviar.",
    tooMuch: "Eso supera tu saldo de créditos.",
    sentPending: (email: string) => `Enviado — esperando que ${email} se una.`,
    sentOk: (amount: string, email: string) => `Enviaste ${amount} a ${email}.`,
    sendFail: "No se pudieron enviar los créditos.",
    sentTo: "Enviado a",
    from: "De",
    waitingJoin: "Esperando que se unan",
    loadingTickets: "Cargando boletos…",
    loadTicketsFail: "No se pudieron cargar tus boletos.",
    noTickets: "Aún no hay pedidos de boletos.",
    whatsOn: "Cartelera",
    ticketCount: (n: number) => `${n} boleto${n === 1 ? "" : "s"}`,
    viewTickets: "Ver boletos",
    firstName: "Nombre",
    lastName: "Apellido",
    phone: "Teléfono",
    saved: "Guardado",
    saveFail: "No se pudo guardar. Intenta de nuevo.",
    saveProfile: "Guardar perfil",
    saving: "Guardando…",
    fromDate: "desde",
    until: "hasta",
  },
} as const;

function formatDate(iso: string | null | undefined, locale: Locale) {
  if (!iso) return "—";
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

function TicketMark() {
  return (
    <svg className="credit-ticket-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M4.5 7.25A2.25 2.25 0 0 1 6.75 5h10.5A2.25 2.25 0 0 1 19.5 7.25v2.1a1.75 1.75 0 0 0 0 3.3v2.1A2.25 2.25 0 0 1 17.25 17H6.75A2.25 2.25 0 0 1 4.5 14.75v-2.1a1.75 1.75 0 0 0 0-3.3v-2.1Zm4.25-.5v10.5h1.5V6.75h-1.5Z"
      />
    </svg>
  );
}

function CreditAmount({
  cents,
  locale,
  signed,
}: {
  cents: number;
  locale: Locale;
  signed?: "plus" | "minus";
}) {
  return (
    <span className="credit-amount">
      {signed === "minus" ? "−" : signed === "plus" ? "+" : null}
      <TicketMark />
      {formatCreditNumber(cents, locale)}
    </span>
  );
}

function formatCredits(cents: number, locale: Locale) {
  return `🎫 ${formatCreditNumber(cents, locale)}`;
}

function fanErrorMessage(err: unknown, fallback: string) {
  if (!(err instanceof Error)) return fallback;
  const json = err.message.match(/\{.*\}/);
  if (json) {
    try {
      const parsed = JSON.parse(json[0]) as { error?: string };
      if (parsed.error) return parsed.error;
    } catch {
      /* ignore */
    }
  }
  return err.message || fallback;
}

function formatStatus(status: string) {
  const cleaned = status.replace(/_/g, " ").trim();
  if (!cleaned) return status;
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

function AccountShell({
  view,
  locale,
  returnUrl,
}: {
  view: AccountView;
  locale: Locale;
  returnUrl: string;
}) {
  const t = copy[locale];
  const paths = membershipPaths(locale);
  const nav = [
    { view: "membership" as const, href: paths.account, label: t.nav.membership },
    { view: "tickets" as const, href: paths.accountTickets, label: t.nav.tickets },
    { view: "profile" as const, href: paths.accountProfile, label: t.nav.profile },
  ];
  const { client, isSignedIn, signOut } = useKintanaAuth();
  const [profile, setProfile] = useState<KintanaFanAccountProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isSignedIn) {
      const next =
        typeof window !== "undefined" ? window.location.pathname : paths.account;
      window.location.assign(signInUrlWithNext(locale, next));
      return;
    }

    let alive = true;
    setLoading(true);
    setError("");

    void client
      .getFanAccountProfile()
      .then((p) => {
        if (!alive) return;
        setProfile(p);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : t.loadAccountFail);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [client, isSignedIn, locale, paths.account, t.loadAccountFail]);

  function onSignOut() {
    signOut();
    window.location.assign(paths.accountSignIn);
  }

  if (loading) {
    return <p className="account-status-copy">{t.loadingAccount}</p>;
  }

  if (error) {
    return (
      <div className="account-shell">
        <p className="form-error">{error}</p>
        <button type="button" className="form-link-button" onClick={onSignOut}>
          {t.signOut}
        </button>
      </div>
    );
  }

  return (
    <div className="account-shell">
      <header className="account-shell-head">
        <div>
          <h1 className="account-title">{t.titles[view]}</h1>
          {profile?.email ? <p className="account-email">{profile.email}</p> : null}
        </div>
        <button type="button" className="form-link-button" onClick={onSignOut}>
          {t.signOut}
        </button>
      </header>

      <nav className="account-subnav" aria-label={t.titles.membership}>
        {nav.map((item) => (
          <a
            key={item.view}
            href={item.href}
            aria-current={item.view === view ? "page" : undefined}
          >
            {item.label}
          </a>
        ))}
      </nav>

      {view === "membership" ? <MembershipView locale={locale} returnUrl={returnUrl} /> : null}
      {view === "tickets" ? <TicketsView locale={locale} /> : null}
      {view === "profile" ? (
        <ProfileView locale={locale} profile={profile} onProfileUpdated={setProfile} />
      ) : null}
    </div>
  );
}

function MembershipView({ locale, returnUrl }: { locale: Locale; returnUrl: string }) {
  const t = copy[locale];
  const paths = membershipPaths(locale);
  const { client } = useKintanaAuth();
  const [membership, setMembership] = useState<KintanaFanMembershipStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingMsg, setBillingMsg] = useState("");
  const [justJoined, setJustJoined] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setJustJoined(new URLSearchParams(window.location.search).get("membership") === "1");
    }

    let alive = true;
    setLoading(true);
    setError("");

    void client
      .getFanMembershipStatus()
      .then((m) => {
        if (!alive) return;
        setMembership(m);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : t.loadMembershipFail);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [client, t.loadMembershipFail]);

  async function reloadMembership() {
    const m = await client.getFanMembershipStatus();
    setMembership(m);
  }

  async function onManageBilling() {
    setBillingLoading(true);
    setBillingMsg("");
    try {
      const { url } = await client.openFanBillingPortal({ returnUrl });
      window.location.assign(url);
    } catch {
      setBillingMsg(t.billingUnavailable);
    } finally {
      setBillingLoading(false);
    }
  }

  if (loading) {
    return <p className="account-status-copy">{t.loadingMembership}</p>;
  }

  if (error) {
    return <p className="form-error">{error}</p>;
  }

  const activeMemberships = membership?.memberships ?? [];

  return (
    <section className="account-panel">
      {justJoined ? <p className="account-flash">{t.flashJoined}</p> : null}

      {activeMemberships.length ? (
        <ul className="account-plan-list">
          {activeMemberships.map((m) => (
            <li key={m.id} className="account-plan">
              <p className="account-plan-name">{m.plan.name}</p>
              <p className="account-plan-meta">
                {formatStatus(m.status)} · {t.fromDate} {formatDate(m.startsAt, locale)}
                {m.endsAt ? ` · ${t.until} ${formatDate(m.endsAt, locale)}` : ""}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <div className="account-empty">
          <p>{t.notMember}</p>
          <a href={`${paths.membership}#join`} className="btn-brand account-action">
            {t.joinNow}
          </a>
        </div>
      )}

      <ActivationCodeRedeemForm
        client={client}
        locale={locale}
        className="account-activation-code mt-6 border-t border-neutral-200 pt-6"
        onRedeemed={reloadMembership}
      />

      {membership?.billing.hasRecurringSubscription ? (
        <button
          type="button"
          className="btn-outline account-action"
          disabled={billingLoading}
          onClick={() => void onManageBilling()}
        >
          {billingLoading ? t.opening : t.manageBilling}
        </button>
      ) : null}

      {billingMsg ? <p className="form-error">{billingMsg}</p> : null}

      {activeMemberships.length || (membership?.walletCreditBalanceCents ?? 0) > 0 ? (
        <IguanaCredits
          locale={locale}
          memberships={activeMemberships}
          walletCreditBalanceCents={membership?.walletCreditBalanceCents ?? 0}
          pendingReceivedCents={membership?.pendingReceivedCents ?? 0}
          onBalanceRefresh={reloadMembership}
        />
      ) : membership && (membership.pendingReceivedCents ?? 0) > 0 ? (
        <p className="account-credits-pending">
          {t.creditsPending(formatCredits(membership.pendingReceivedCents ?? 0, locale))}
        </p>
      ) : null}
    </section>
  );
}

function IguanaCredits({
  locale,
  memberships,
  walletCreditBalanceCents,
  pendingReceivedCents,
  onBalanceRefresh,
}: {
  locale: Locale;
  memberships: NonNullable<KintanaFanMembershipStatus["memberships"]>;
  walletCreditBalanceCents: number;
  pendingReceivedCents: number;
  onBalanceRefresh?: () => void | Promise<void>;
}) {
  const t = copy[locale];
  const { client } = useKintanaAuth();
  const [transfers, setTransfers] = useState<KintanaFanCreditTransfer[]>([]);
  const [toEmail, setToEmail] = useState("");
  const [amount, setAmount] = useState("");
  const [sending, setSending] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgError, setMsgError] = useState(false);
  const [balances, setBalances] = useState(memberships);
  const [walletBalance, setWalletBalance] = useState(walletCreditBalanceCents);

  const memberCreditCents = balances.reduce((s, m) => s + (m.creditBalanceCents ?? 0), 0);
  const totalCents = memberCreditCents + walletBalance;
  const canSend = totalCents > 0;

  useEffect(() => {
    setBalances(memberships);
    setWalletBalance(walletCreditBalanceCents);
  }, [memberships, walletCreditBalanceCents]);

  useEffect(() => {
    let alive = true;
    void client
      .listFanMembershipCreditTransfers()
      .then((rows) => {
        if (alive) setTransfers(rows);
      })
      .catch(() => {
        if (alive) setTransfers([]);
      });
    return () => {
      alive = false;
    };
  }, [client]);

  async function onSend(e: React.FormEvent) {
    e.preventDefault();
    const dollars = Number(amount);
    if (!Number.isFinite(dollars) || dollars <= 0) {
      setMsg(t.enterAmount);
      setMsgError(true);
      return;
    }
    const amountCents = Math.round(dollars * 100);
    if (amountCents > totalCents) {
      setMsg(t.tooMuch);
      setMsgError(true);
      return;
    }
    setSending(true);
    setMsg("");
    setMsgError(false);
    try {
      const result = await client.transferFanMembershipCredits({ amountCents, toEmail });
      const status = await client.getFanMembershipStatus();
      setBalances(status.memberships);
      setWalletBalance(status.walletCreditBalanceCents ?? 0);
      const history = await client.listFanMembershipCreditTransfers();
      setTransfers(history);
      await onBalanceRefresh?.();
      setToEmail("");
      setAmount("");
      setMsg(
        result.status === "PENDING"
          ? t.sentPending(result.toEmail)
          : t.sentOk(formatCredits(result.amountCents, locale), result.toEmail)
      );
    } catch (err) {
      setMsg(fanErrorMessage(err, t.sendFail));
      setMsgError(true);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="account-credits">
      <h2 className="account-credits-title">{t.creditsTitle}</h2>
      <p className="account-credits-balance">
        <CreditAmount cents={totalCents} locale={locale} />
      </p>
      <p className="account-credits-note">{t.creditsNote}</p>
      {pendingReceivedCents > 0 ? (
        <p className="account-credits-pending">
          {t.creditsPendingLand(formatCredits(pendingReceivedCents, locale))}
        </p>
      ) : null}

      {canSend ? (
        <form className="account-form account-credits-form" onSubmit={(e) => void onSend(e)}>
          <label>
            {t.sendTo}
            <input
              type="email"
              autoComplete="email"
              value={toEmail}
              onChange={(e) => setToEmail(e.target.value)}
              required
            />
          </label>
          <label>
            {t.amount}
            <input
              type="number"
              inputMode="decimal"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
          </label>
          {msg ? <p className={msgError ? "form-error" : "account-form-msg"}>{msg}</p> : null}
          <button type="submit" className="btn-brand account-action" disabled={sending}>
            {sending ? t.sending : t.sendCredits}
          </button>
        </form>
      ) : (
        <p className="account-credits-empty">{t.noCredits}</p>
      )}

      {transfers.length ? (
        <ul className="account-credits-history">
          {transfers.map((tr) => (
            <li key={tr.id}>
              <span>
                {tr.direction === "sent" ? t.sentTo : t.from}{" "}
                {tr.counterpartyName || tr.counterpartyEmail}
              </span>
              <span className="account-credits-history-amt">
                <CreditAmount
                  cents={tr.amountCents}
                  locale={locale}
                  signed={tr.direction === "sent" ? "minus" : "plus"}
                />
              </span>
              {tr.status === "PENDING" && tr.direction === "sent" ? (
                <span className="account-credits-history-status">{t.waitingJoin}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function TicketsView({ locale }: { locale: Locale }) {
  const t = copy[locale];
  const paths = membershipPaths(locale);
  const { client } = useKintanaAuth();
  const [tickets, setTickets] = useState<KintanaFanTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");

    void client
      .listFanTickets()
      .then((rows) => {
        if (!alive) return;
        setTickets(rows);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : t.loadTicketsFail);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [client, t.loadTicketsFail]);

  if (loading) {
    return <p className="account-status-copy">{t.loadingTickets}</p>;
  }

  if (error) {
    return <p className="form-error">{error}</p>;
  }

  if (!tickets.length) {
    return (
      <section className="account-panel">
        <div className="account-empty">
          <p>{t.noTickets}</p>
          <a href={paths.events} className="btn-brand account-action">
            {t.whatsOn}
          </a>
        </div>
      </section>
    );
  }

  return (
    <section className="account-panel">
      <ul className="account-ticket-list">
        {tickets.map((order) => (
          <li key={order.id} className="account-ticket">
            <div className="account-ticket-row">
              <p className="account-ticket-name">{order.event.name}</p>
              <p className="account-ticket-date">{formatDate(order.event.date, locale)}</p>
            </div>
            <p className="account-ticket-meta">{t.ticketCount(order.tickets.length)}</p>
            {order.ticketsPageUrl ? (
              <a href={order.ticketsPageUrl} className="account-ticket-link">
                {t.viewTickets}
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

function ProfileView({
  locale,
  profile,
  onProfileUpdated,
}: {
  locale: Locale;
  profile: KintanaFanAccountProfile | null;
  onProfileUpdated: (profile: KintanaFanAccountProfile) => void;
}) {
  const t = copy[locale];
  const { client } = useKintanaAuth();
  const [firstName, setFirstName] = useState(profile?.firstName ?? "");
  const [lastName, setLastName] = useState(profile?.lastName ?? "");
  const [phone, setPhone] = useState(profile?.phone ?? "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgError, setMsgError] = useState(false);

  async function onProfileSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMsg("");
    setMsgError(false);
    try {
      const updated = await client.updateFanAccountProfile({ firstName, lastName, phone });
      onProfileUpdated(updated);
      setMsg(t.saved);
    } catch {
      setMsg(t.saveFail);
      setMsgError(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="account-panel">
      <form className="account-form" onSubmit={(e) => void onProfileSave(e)}>
        <label>
          {t.firstName}
          <input
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            autoComplete="given-name"
          />
        </label>
        <label>
          {t.lastName}
          <input
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            autoComplete="family-name"
          />
        </label>
        <label>
          {t.phone}
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            autoComplete="tel"
          />
        </label>
        {msg ? <p className={msgError ? "form-error" : "account-form-msg"}>{msg}</p> : null}
        <button type="submit" className="btn-brand account-action" disabled={saving}>
          {saving ? t.saving : t.saveProfile}
        </button>
      </form>
    </section>
  );
}

export function AccountPage({ apiKey, baseUrl, locale, view }: Props) {
  const returnUrl =
    typeof window !== "undefined"
      ? `${window.location.origin.replace(/\/$/, "")}${membershipPaths(locale).account}`
      : accountReturnUrl(locale);
  return (
    <KintanaAuthProvider apiKey={apiKey} baseUrl={baseUrl}>
      <AccountShell view={view} locale={locale} returnUrl={returnUrl} />
    </KintanaAuthProvider>
  );
}
