"use client";

import { useEffect, useState } from "react";
import type { KintanaFanEventDetail } from "@kintana/sdk";
import { KintanaAuthProvider, useKintanaAuth } from "@kintana/sdk/react";
import { numberLocale } from "../../lib/kintana-auth";
import type { Locale } from "../../i18n/routes";

type Props = {
  apiKey: string;
  baseUrl: string;
  locale: Locale;
  slug: string;
  membershipHref: string;
};

const copy = {
  en: {
    memberPricing: "You're a member — member pricing applies at checkout where available.",
    membersOnlyShow: "This show is for members.",
    join: "Join membership",
    toBook: "to book.",
    membersPay: (member: string, usual: string) =>
      `Members pay ${member} (usually ${usual}).`,
    someMembersOnly: "Some ticket types are members only.",
  },
  es: {
    memberPricing: "Eres miembro — el precio de miembro aplica en el checkout cuando esté disponible.",
    membersOnlyShow: "Este show es solo para miembros.",
    join: "Únete a la membresía",
    toBook: "para reservar.",
    membersPay: (member: string, usual: string) =>
      `Los miembros pagan ${member} (normalmente ${usual}).`,
    someMembersOnly: "Algunos tipos de boleto son solo para miembros.",
  },
} as const;

function formatPrice(cents: number, currency: string, locale: Locale) {
  try {
    return new Intl.NumberFormat(numberLocale(locale), {
      style: "currency",
      currency: currency.toUpperCase(),
    }).format(cents / 100);
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency.toUpperCase()}`;
  }
}

function EventMemberOfferInner({
  slug,
  locale,
  membershipHref,
}: {
  slug: string;
  locale: Locale;
  membershipHref: string;
}) {
  const t = copy[locale];
  const { client, isSignedIn } = useKintanaAuth();
  const [event, setEvent] = useState<KintanaFanEventDetail | null>(null);

  useEffect(() => {
    let alive = true;
    void client
      .getFanEvent(slug)
      .then((detail) => {
        if (alive) setEvent(detail);
      })
      .catch(() => {
        if (alive) setEvent(null);
      });
    return () => {
      alive = false;
    };
  }, [client, isSignedIn, slug]);

  if (!event) return null;

  const memberTickets = event.ticketTypes.filter(
    (tt) =>
      tt.memberAccess === "MEMBERS_ONLY" ||
      tt.memberAccess === "MEMBER_DISCOUNT" ||
      tt.memberAccess === "MEMBER_FREE"
  );

  if (event.isMember) {
    const savings = memberTickets.filter(
      (tt) =>
        tt.memberAccess === "MEMBER_DISCOUNT" &&
        typeof tt.yourPriceCents === "number" &&
        tt.yourPriceCents < tt.priceCents
    );
    if (!savings.length) return null;
    return <p className="event-member-offer mt-3 text-sm text-neutral-800">{t.memberPricing}</p>;
  }

  if (event.visibility === "MEMBERS_ONLY") {
    return (
      <p className="event-member-offer mt-3 text-sm text-neutral-800">
        {t.membersOnlyShow}{" "}
        <a href={membershipHref} className="text-brand hover:underline">
          {t.join}
        </a>{" "}
        {t.toBook}
      </p>
    );
  }

  const discount = memberTickets.find(
    (tt) =>
      tt.memberAccess === "MEMBER_DISCOUNT" &&
      typeof tt.memberPriceCents === "number" &&
      tt.memberPriceCents < tt.priceCents
  );

  if (discount?.memberPriceCents != null) {
    return (
      <p className="event-member-offer mt-3 text-sm text-neutral-800">
        {t.membersPay(
          formatPrice(discount.memberPriceCents, discount.currency, locale),
          formatPrice(discount.priceCents, discount.currency, locale)
        )}{" "}
        <a href={membershipHref} className="text-brand hover:underline">
          {t.join}
        </a>
      </p>
    );
  }

  const membersOnly = memberTickets.some((tt) => tt.memberAccess === "MEMBERS_ONLY");
  if (membersOnly) {
    return (
      <p className="event-member-offer mt-3 text-sm text-neutral-800">
        {t.someMembersOnly}{" "}
        <a href={membershipHref} className="text-brand hover:underline">
          {t.join}
        </a>
      </p>
    );
  }

  return null;
}

export function EventMemberOffer({ apiKey, baseUrl, locale, slug, membershipHref }: Props) {
  return (
    <KintanaAuthProvider apiKey={apiKey} baseUrl={baseUrl}>
      <EventMemberOfferInner slug={slug} locale={locale} membershipHref={membershipHref} />
    </KintanaAuthProvider>
  );
}
