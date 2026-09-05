"use client";

import { useEffect, useState } from "react";
import { loadStripe, type Stripe } from "@stripe/stripe-js";
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";
import type { KintanaFanMembershipPlan, KintanaFanMembershipStatus } from "@kintana/sdk";
import { KintanaAuthProvider, useKintanaAuth } from "@kintana/sdk/react";
import { membershipContent } from "../../content/membership";
import { ActivationCodeRedeemForm } from "./ActivationCodeRedeemForm";
import {
  membershipCancelUrl,
  membershipPaths,
  membershipSuccessUrl,
  numberLocale,
  signInUrlWithNext,
} from "../../lib/kintana-auth";
import type { Locale } from "../../i18n/routes";

type Props = {
  apiKey: string;
  baseUrl: string;
  locale: Locale;
};

type SubscribeInterval = "month" | "year";

type ElementsPayPayload = {
  clientSecret: string;
  stripeConnectAccountId: string | null;
  stripePublishableKey: string | null;
};

const ui = {
  en: {
    completePayment: (name: string) => (
      <>
        Complete payment for <strong>{name}</strong>.
      </>
    ),
    payNow: "Pay now",
    processing: "Processing…",
    back: "Back",
    backToPlans: "Back to plans",
    loading: "Loading…",
    loadingPayment: "Loading payment…",
    paymentNotConfigured: "Payment is not configured for this plan.",
    paymentFailed: "Payment failed.",
    startPaymentFail: "Could not start payment.",
    monthly: "Monthly",
    yearly: "Yearly",
    switchToMonthly: "Switch to monthly billing",
    switchToYearly: "Switch to yearly billing",
    billingPeriod: "Billing period",
    perMonth: "per month",
    perMonthYearly: "per month, billed yearly",
    billedYearly: (price: string) => `${price} billed once a year`,
    pctOff: (n: number) => `${n}% off`,
    youHaveThis: "You have this membership.",
    joinNow: "Join now",
    loadingJoin: "Loading…",
    lifetime: (price: string) => `Lifetime · ${price}`,
    dayPass: (days: number, price: string) => `${days}-day pass · ${price}`,
    notAvailable: "Not available online.",
    signInBefore: "You’ll sign in before checkout.",
    loadingOptions: "Loading membership options…",
    notAvailableNow: "Membership is not available right now.",
    noPlans: "No membership plans are listed yet.",
    youreA: (names: string) => (
      <>
        You’re a {names} member.{" "}
      </>
    ),
    manageAccount: "Manage in your account",
    alreadyMember: "Already a member?",
    signIn: "Sign in",
    loadSettingsFail: "Could not load membership settings.",
    loadPlansFail: "Could not load membership plans.",
    startCheckoutFail: "Could not start checkout.",
  },
  es: {
    completePayment: (name: string) => (
      <>
        Completa el pago de <strong>{name}</strong>.
      </>
    ),
    payNow: "Pagar ahora",
    processing: "Procesando…",
    back: "Atrás",
    backToPlans: "Volver a los planes",
    loading: "Cargando…",
    loadingPayment: "Cargando pago…",
    paymentNotConfigured: "El pago no está configurado para este plan.",
    paymentFailed: "El pago falló.",
    startPaymentFail: "No se pudo iniciar el pago.",
    monthly: "Mensual",
    yearly: "Anual",
    switchToMonthly: "Cambiar a facturación mensual",
    switchToYearly: "Cambiar a facturación anual",
    billingPeriod: "Periodo de facturación",
    perMonth: "al mes",
    perMonthYearly: "al mes, facturado anualmente",
    billedYearly: (price: string) => `${price} facturado una vez al año`,
    pctOff: (n: number) => `${n}% menos`,
    youHaveThis: "Ya tienes esta membresía.",
    joinNow: "Únete ahora",
    loadingJoin: "Cargando…",
    lifetime: (price: string) => `De por vida · ${price}`,
    dayPass: (days: number, price: string) => `Pase de ${days} días · ${price}`,
    notAvailable: "No disponible en línea.",
    signInBefore: "Iniciarás sesión antes del pago.",
    loadingOptions: "Cargando opciones de membresía…",
    notAvailableNow: "La membresía no está disponible ahora.",
    noPlans: "Aún no hay planes de membresía listados.",
    youreA: (names: string) => (
      <>
        Eres miembro {names}.{" "}
      </>
    ),
    manageAccount: "Administrar en tu cuenta",
    alreadyMember: "¿Ya eres miembro?",
    signIn: "Iniciar sesión",
    loadSettingsFail: "No se pudieron cargar los ajustes de membresía.",
    loadPlansFail: "No se pudieron cargar los planes de membresía.",
    startCheckoutFail: "No se pudo iniciar el checkout.",
  },
} as const;

function formatPrice(cents: number, currency: string, locale: Locale) {
  try {
    return new Intl.NumberFormat(numberLocale(locale), {
      style: "currency",
      currency: currency.toUpperCase(),
      maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
    }).format(cents / 100);
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency.toUpperCase()}`;
  }
}

function planBenefits(plan: KintanaFanMembershipPlan, locale: Locale): string[] {
  const fromApi = (plan.benefits ?? []).map((b) => b.label).filter(Boolean);
  if (fromApi.length) return fromApi;
  return [...membershipContent[locale].defaultBenefitLabels];
}

function MembershipPaymentForm({
  planName,
  locale,
  onBack,
  onComplete,
}: {
  planName: string;
  locale: Locale;
  onBack: () => void;
  onComplete: () => void;
}) {
  const t = ui[locale];
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!stripe || !elements) return;
    setBusy(true);
    setError("");
    const { error: submitError } = await stripe.confirmPayment({
      elements,
      confirmParams: { return_url: membershipSuccessUrl(locale) },
      redirect: "if_required",
    });
    if (submitError) {
      setError(submitError.message ?? t.paymentFailed);
      setBusy(false);
      return;
    }
    onComplete();
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
      <p className="text-muted">{t.completePayment(planName)}</p>
      <PaymentElement />
      {error ? <p className="form-error">{error}</p> : null}
      <div className="flex flex-wrap gap-3">
        <button type="submit" className="btn-brand" disabled={!stripe || busy}>
          {busy ? t.processing : t.payNow}
        </button>
        <button type="button" className="form-link-button" onClick={onBack} disabled={busy}>
          {t.back}
        </button>
      </div>
    </form>
  );
}

function ElementsCheckout({
  payload,
  planName,
  locale,
  onBack,
  onComplete,
}: {
  payload: ElementsPayPayload;
  planName: string;
  locale: Locale;
  onBack: () => void;
  onComplete: () => void;
}) {
  const t = ui[locale];
  const [stripe, setStripe] = useState<Stripe | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    if (!payload.stripePublishableKey) {
      setError(t.paymentNotConfigured);
      return;
    }
    void (payload.stripeConnectAccountId
      ? loadStripe(payload.stripePublishableKey, { stripeAccount: payload.stripeConnectAccountId })
      : loadStripe(payload.stripePublishableKey)
    ).then((loaded) => {
      if (alive) setStripe(loaded);
    });
    return () => {
      alive = false;
    };
  }, [payload.clientSecret, payload.stripeConnectAccountId, payload.stripePublishableKey, t.paymentNotConfigured]);

  if (error) {
    return (
      <div>
        <p className="form-error">{error}</p>
        <button type="button" className="form-link-button" onClick={onBack}>
          {t.backToPlans}
        </button>
      </div>
    );
  }
  if (!stripe) return <p className="text-muted">{t.loading}</p>;

  return (
    <Elements stripe={stripe} options={{ clientSecret: payload.clientSecret }}>
      <MembershipPaymentForm
        planName={planName}
        locale={locale}
        onBack={onBack}
        onComplete={onComplete}
      />
    </Elements>
  );
}

function OneoffCheckout({
  planId,
  planName,
  kind,
  locale,
  onBack,
  onComplete,
}: {
  planId: string;
  planName: string;
  kind: "lifetime" | "pass";
  locale: Locale;
  onBack: () => void;
  onComplete: () => void;
}) {
  const t = ui[locale];
  const { client } = useKintanaAuth();
  const [payload, setPayload] = useState<ElementsPayPayload | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    void client
      .createFanOneoffMembershipPayment({ planId, kind })
      .then((res) => {
        if (!alive) return;
        if (!res.stripePublishableKey) {
          setError(t.paymentNotConfigured);
          return;
        }
        setPayload({
          clientSecret: res.clientSecret,
          stripeConnectAccountId: res.stripeConnectAccountId,
          stripePublishableKey: res.stripePublishableKey,
        });
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : t.startPaymentFail);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [client, planId, kind, t.paymentNotConfigured, t.startPaymentFail]);

  if (loading && !payload) {
    return <p className="text-muted">{t.loadingPayment}</p>;
  }

  if (!payload) {
    return (
      <div>
        {error ? <p className="form-error">{error}</p> : null}
        <button type="button" className="form-link-button" onClick={onBack}>
          {t.backToPlans}
        </button>
      </div>
    );
  }

  return (
    <ElementsCheckout
      payload={payload}
      planName={planName}
      locale={locale}
      onBack={onBack}
      onComplete={onComplete}
    />
  );
}

function annualDiscountPercent(monthlyCents: number, annualCents: number): number | null {
  const yearAtMonthly = monthlyCents * 12;
  if (yearAtMonthly <= 0 || annualCents >= yearAtMonthly) return null;
  return Math.max(1, Math.round((1 - annualCents / yearAtMonthly) * 100));
}

function PlanCheckout({
  plan,
  isActive,
  isSignedIn,
  actionKey,
  locale,
  membershipHref,
  onSubscribe,
  onBuyOneoff,
}: {
  plan: KintanaFanMembershipPlan;
  isActive: boolean;
  isSignedIn: boolean;
  actionKey: string | null;
  locale: Locale;
  membershipHref: string;
  onSubscribe: (planId: string, interval: SubscribeInterval) => void;
  onBuyOneoff: (plan: KintanaFanMembershipPlan, kind: "lifetime" | "pass") => void;
}) {
  const t = ui[locale];
  const monthly = plan.prices?.monthly?.amountCents;
  const annual = plan.prices?.annual?.amountCents;
  const lifetime = plan.prices?.lifetime?.amountCents;
  const pass = plan.prices?.pass;
  const benefits = planBenefits(plan, locale);
  const hasMonthly = typeof monthly === "number";
  const hasAnnual = typeof annual === "number";
  const hasRecurring = hasMonthly || hasAnnual;
  const bothIntervals = hasMonthly && hasAnnual;
  const discountPct =
    hasMonthly && hasAnnual ? annualDiscountPercent(monthly, annual) : null;

  const [interval, setInterval] = useState<SubscribeInterval>(
    hasAnnual && !hasMonthly ? "year" : "month"
  );

  const activeInterval: SubscribeInterval =
    interval === "year" && hasAnnual ? "year" : hasMonthly ? "month" : "year";

  const displayCents =
    activeInterval === "year" && hasAnnual
      ? Math.round(annual / 12)
      : hasMonthly
        ? monthly
        : annual;
  const displaySuffix =
    activeInterval === "year" && hasAnnual ? t.perMonthYearly : t.perMonth;
  const joinBusy = actionKey === `${plan.id}:${activeInterval}`;

  return (
    <article className="membership-plan-block">
      {bothIntervals && !isActive ? (
        <div className="membership-billing-toggle" role="group" aria-label={t.billingPeriod}>
          <button
            type="button"
            className={
              activeInterval === "month"
                ? "membership-billing-label is-active"
                : "membership-billing-label"
            }
            onClick={() => setInterval("month")}
          >
            {t.monthly}
          </button>
          <button
            type="button"
            className={
              activeInterval === "year"
                ? "membership-billing-switch is-yearly"
                : "membership-billing-switch"
            }
            aria-pressed={activeInterval === "year"}
            aria-label={activeInterval === "year" ? t.switchToMonthly : t.switchToYearly}
            onClick={() => setInterval(activeInterval === "year" ? "month" : "year")}
          >
            <span className="membership-billing-knob" aria-hidden="true" />
          </button>
          <button
            type="button"
            className={
              activeInterval === "year"
                ? "membership-billing-label is-active"
                : "membership-billing-label"
            }
            onClick={() => setInterval("year")}
          >
            {t.yearly}
          </button>
          {discountPct != null ? (
            <span className="membership-discount-badge">{t.pctOff(discountPct)}</span>
          ) : null}
        </div>
      ) : null}

      <div className="membership-plan-panel">
        <div className="membership-plan-panel-copy">
          <h3 className="font-display text-2xl text-neutral-950 sm:text-3xl">{plan.name}</h3>
          {plan.description ? <p className="mt-2 text-muted">{plan.description}</p> : null}

          {!isActive && hasRecurring && displayCents != null ? (
            <div className="membership-plan-price">
              <p className="membership-plan-amount">
                {formatPrice(displayCents, plan.currency, locale)}
              </p>
              <p className="membership-plan-cadence">{displaySuffix}</p>
              {activeInterval === "year" && hasAnnual ? (
                <p className="membership-plan-billed">
                  {t.billedYearly(formatPrice(annual, plan.currency, locale))}
                </p>
              ) : null}
            </div>
          ) : null}

          <ul className="membership-plan-benefits">
            {benefits.map((label) => (
              <li key={label}>
                <span className="membership-plan-check" aria-hidden="true">
                  ✓
                </span>
                <span>{label}</span>
              </li>
            ))}
          </ul>
        </div>

        {isActive ? (
          <p className="mt-6 text-sm text-muted">{t.youHaveThis}</p>
        ) : (
          <div className="membership-plan-actions">
            {hasRecurring ? (
              <button
                type="button"
                className="btn-brand membership-join-btn membership-join-btn-primary"
                disabled={joinBusy}
                onClick={() => onSubscribe(plan.id, activeInterval)}
              >
                {joinBusy ? t.loadingJoin : t.joinNow}
              </button>
            ) : null}
            {typeof lifetime === "number" ? (
              <button
                type="button"
                className="btn-outline membership-join-btn"
                onClick={() => {
                  if (!isSignedIn) {
                    window.location.assign(signInUrlWithNext(locale, membershipHref));
                    return;
                  }
                  onBuyOneoff(plan, "lifetime");
                }}
              >
                {t.lifetime(formatPrice(lifetime, plan.currency, locale))}
              </button>
            ) : null}
            {pass ? (
              <button
                type="button"
                className="btn-outline membership-join-btn"
                onClick={() => {
                  if (!isSignedIn) {
                    window.location.assign(signInUrlWithNext(locale, membershipHref));
                    return;
                  }
                  onBuyOneoff(plan, "pass");
                }}
              >
                {t.dayPass(pass.durationDays, formatPrice(pass.amountCents, plan.currency, locale))}
              </button>
            ) : null}
            {!hasRecurring && lifetime == null && !pass ? (
              <p className="text-sm text-muted">{t.notAvailable}</p>
            ) : null}
          </div>
        )}

        {!isSignedIn && !isActive && hasRecurring ? (
          <p className="mt-3 text-sm text-muted">{t.signInBefore}</p>
        ) : null}
      </div>
    </article>
  );
}

function MembershipPageInner({ locale }: { locale: Locale }) {
  const t = ui[locale];
  const paths = membershipPaths(locale);
  const { client, isSignedIn } = useKintanaAuth();
  const [plans, setPlans] = useState<KintanaFanMembershipPlan[]>([]);
  const [status, setStatus] = useState<KintanaFanMembershipStatus | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [oneoff, setOneoff] = useState<{
    plan: KintanaFanMembershipPlan;
    kind: "lifetime" | "pass";
  } | null>(null);
  const [subscriptionPay, setSubscriptionPay] = useState<{
    planName: string;
    payload: ElementsPayPayload;
  } | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");

    void client
      .getFanConfig()
      .then((config) => {
        if (!alive) return;
        setEnabled(config.membershipsEnabled && config.memberPortalEnabled);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : t.loadSettingsFail);
      });

    void client
      .listFanMembershipPlans()
      .then((listedPlans) => {
        if (!alive) return;
        setPlans(listedPlans);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setError(err instanceof Error ? err.message : t.loadPlansFail);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    if (isSignedIn) {
      void client
        .getFanMembershipStatus()
        .then((membershipStatus) => {
          if (!alive) return;
          setStatus(membershipStatus);
        })
        .catch(() => {
          if (!alive) return;
          setStatus(null);
        });
    } else {
      setStatus(null);
    }

    return () => {
      alive = false;
    };
  }, [client, isSignedIn, t.loadPlansFail, t.loadSettingsFail]);

  async function onSubscribe(planId: string, interval: SubscribeInterval) {
    if (!isSignedIn) {
      window.location.assign(signInUrlWithNext(locale, paths.membership));
      return;
    }
    setActionKey(`${planId}:${interval}`);
    setError("");
    try {
      const res = await client.subscribeFanMembership({
        planId,
        interval,
        successUrl: membershipSuccessUrl(locale),
        cancelUrl: membershipCancelUrl(locale),
      });
      if (!res.clientSecret || !res.stripePublishableKey) {
        throw new Error(t.paymentNotConfigured);
      }
      const planName = plans.find((p) => p.id === planId)?.name ?? "membership";
      setSubscriptionPay({
        planName,
        payload: {
          clientSecret: res.clientSecret,
          stripeConnectAccountId: res.stripeConnectAccountId,
          stripePublishableKey: res.stripePublishableKey,
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : t.startCheckoutFail);
    } finally {
      setActionKey(null);
    }
  }

  async function reloadStatus() {
    const m = await client.getFanMembershipStatus();
    setStatus(m);
  }

  if (loading) {
    return <p className="text-muted">{t.loadingOptions}</p>;
  }

  if (!enabled) {
    return <p className="text-muted">{t.notAvailableNow}</p>;
  }

  if (subscriptionPay) {
    return (
      <ElementsCheckout
        payload={subscriptionPay.payload}
        planName={subscriptionPay.planName}
        locale={locale}
        onBack={() => setSubscriptionPay(null)}
        onComplete={() => {
          window.location.assign(membershipSuccessUrl(locale));
        }}
      />
    );
  }

  if (oneoff) {
    return (
      <OneoffCheckout
        planId={oneoff.plan.id}
        planName={oneoff.plan.name}
        kind={oneoff.kind}
        locale={locale}
        onBack={() => setOneoff(null)}
        onComplete={() => {
          window.location.assign(membershipSuccessUrl(locale));
        }}
      />
    );
  }

  const activePlanIds = new Set((status?.memberships ?? []).map((m) => m.plan.id));

  return (
    <div className="membership-checkout space-y-10">
      {error ? <p className="form-error">{error}</p> : null}

      {isSignedIn && status?.memberships.length ? (
        <p className="membership-current-line">
          {t.youreA(status.memberships.map((m) => m.plan.name).join(", "))}
          <a href={paths.account}>{t.manageAccount}</a>
        </p>
      ) : null}

      {plans.length === 0 ? (
        <p className="text-muted">{t.noPlans}</p>
      ) : (
        <div className="membership-plans space-y-12">
          {plans.map((plan) => (
            <PlanCheckout
              key={plan.id}
              plan={plan}
              isActive={activePlanIds.has(plan.id)}
              isSignedIn={isSignedIn}
              actionKey={actionKey}
              locale={locale}
              membershipHref={paths.membership}
              onSubscribe={(id, interval) => void onSubscribe(id, interval)}
              onBuyOneoff={(p, kind) => setOneoff({ plan: p, kind })}
            />
          ))}
        </div>
      )}

      {isSignedIn ? (
        <ActivationCodeRedeemForm
          client={client}
          locale={locale}
          className="membership-activation-code border-t border-neutral-200 pt-8"
          onRedeemed={reloadStatus}
        />
      ) : null}

      {!isSignedIn ? (
        <p className="text-sm text-muted">
          {t.alreadyMember}{" "}
          <a href={signInUrlWithNext(locale, paths.membership)} className="text-brand hover:underline">
            {t.signIn}
          </a>
        </p>
      ) : null}
    </div>
  );
}

export function MembershipPage({ apiKey, baseUrl, locale }: Props) {
  return (
    <KintanaAuthProvider apiKey={apiKey} baseUrl={baseUrl}>
      <MembershipPageInner locale={locale} />
    </KintanaAuthProvider>
  );
}
