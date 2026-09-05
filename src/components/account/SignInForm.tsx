"use client";

import { useState } from "react";
import { KintanaAuthProvider, useKintanaAuth } from "@kintana/sdk/react";
import { membershipPaths } from "../../lib/kintana-auth";
import type { Locale } from "../../i18n/routes";

type AuthFormMode = "sign-in" | "register";

type Props = {
  apiKey: string;
  baseUrl: string;
  locale: Locale;
  redirectUrl?: string;
  mode?: AuthFormMode;
  className?: string;
};

const copyByMode: Record<
  Locale,
  Record<
    AuthFormMode,
    {
      emailError: string;
      codeLabel: string;
      sentMessage: string;
      emailButton: string;
      emailButtonLoading: string;
      codeButton: string;
      codeButtonLoading: string;
      emailLabel: string;
      invalidCode: string;
      redirecting: string;
      differentEmail: string;
    }
  >
> = {
  en: {
    "sign-in": {
      emailError: "Could not send sign-in email.",
      codeLabel: "Sign-in code",
      sentMessage: "Check your email for a sign-in link and 6-digit code for",
      emailButton: "Send sign-in code",
      emailButtonLoading: "Sending…",
      codeButton: "Continue",
      codeButtonLoading: "Signing in…",
      emailLabel: "Email",
      invalidCode: "Invalid or expired code.",
      redirecting: "Redirecting…",
      differentEmail: "Use a different email",
    },
    register: {
      emailError: "Could not send confirmation email.",
      codeLabel: "Confirmation code",
      sentMessage: "Check your email for a confirmation link and 6-digit code for",
      emailButton: "Create account",
      emailButtonLoading: "Sending…",
      codeButton: "Continue",
      codeButtonLoading: "Creating account…",
      emailLabel: "Email",
      invalidCode: "Invalid or expired code.",
      redirecting: "Redirecting…",
      differentEmail: "Use a different email",
    },
  },
  es: {
    "sign-in": {
      emailError: "No se pudo enviar el correo de acceso.",
      codeLabel: "Código de acceso",
      sentMessage: "Revisa tu correo: enviamos un enlace y un código de 6 dígitos a",
      emailButton: "Enviar código",
      emailButtonLoading: "Enviando…",
      codeButton: "Continuar",
      codeButtonLoading: "Entrando…",
      emailLabel: "Correo",
      invalidCode: "Código inválido o vencido.",
      redirecting: "Redirigiendo…",
      differentEmail: "Usar otro correo",
    },
    register: {
      emailError: "No se pudo enviar el correo de confirmación.",
      codeLabel: "Código de confirmación",
      sentMessage: "Revisa tu correo: enviamos un enlace y un código de 6 dígitos a",
      emailButton: "Crear cuenta",
      emailButtonLoading: "Enviando…",
      codeButton: "Continuar",
      codeButtonLoading: "Creando cuenta…",
      emailLabel: "Correo",
      invalidCode: "Código inválido o vencido.",
      redirecting: "Redirigiendo…",
      differentEmail: "Usar otro correo",
    },
  },
};

function verifyRedirectUrl(locale: Locale, fallback?: string): string {
  if (typeof window !== "undefined") {
    return `${window.location.origin.replace(/\/$/, "")}${membershipPaths(locale).accountVerify}`;
  }
  return fallback ?? "";
}

function postAuthRedirect(locale: Locale): string {
  if (typeof window === "undefined") return membershipPaths(locale).account;
  const next = new URLSearchParams(window.location.search).get("next")?.trim();
  if (next && next.startsWith("/") && !next.startsWith("//")) return next;
  return membershipPaths(locale).account;
}

function SignInFormInner({
  locale,
  redirectUrl,
  mode = "sign-in",
  className,
}: {
  locale: Locale;
  redirectUrl?: string;
  mode?: AuthFormMode;
  className?: string;
}) {
  const copy = copyByMode[locale][mode];
  const { requestMagicLink, verifyCode, isSignedIn } = useKintanaAuth();
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  if (isSignedIn && typeof window !== "undefined") {
    window.location.assign(postAuthRedirect(locale));
    return <p className="account-status-copy">{copy.redirecting}</p>;
  }

  async function onEmailSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await requestMagicLink(email.trim(), verifyRedirectUrl(locale, redirectUrl));
      setSent(true);
      setStep("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.emailError);
    } finally {
      setLoading(false);
    }
  }

  async function onCodeSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await verifyCode(email.trim(), code.trim());
      window.location.assign(postAuthRedirect(locale));
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.invalidCode);
    } finally {
      setLoading(false);
    }
  }

  if (step === "code") {
    return (
      <div className={className}>
        {sent ? (
          <p className="account-auth-sent">
            {copy.sentMessage} <strong>{email}</strong>.
          </p>
        ) : null}
        <form className="account-auth-form" onSubmit={(e) => void onCodeSubmit(e)}>
          <label>
            {copy.codeLabel}
            <input
              className="account-auth-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              required
              maxLength={6}
              placeholder="000000"
              autoFocus
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button
            type="submit"
            className="btn-brand account-auth-submit"
            disabled={loading || code.length < 6}
          >
            {loading ? copy.codeButtonLoading : copy.codeButton}
          </button>
        </form>
        <button type="button" className="form-link-button" onClick={() => setStep("email")}>
          {copy.differentEmail}
        </button>
      </div>
    );
  }

  return (
    <form
      className={["account-auth-form", className].filter(Boolean).join(" ")}
      onSubmit={(e) => void onEmailSubmit(e)}
    >
      <label>
        {copy.emailLabel}
        <input
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </label>
      {error ? <p className="form-error">{error}</p> : null}
      <button type="submit" className="btn-brand account-auth-submit" disabled={loading}>
        {loading ? copy.emailButtonLoading : copy.emailButton}
      </button>
    </form>
  );
}

export function SignInForm({ apiKey, baseUrl, locale, redirectUrl, mode, className }: Props) {
  return (
    <KintanaAuthProvider apiKey={apiKey} baseUrl={baseUrl}>
      <SignInFormInner
        locale={locale}
        redirectUrl={redirectUrl}
        mode={mode}
        className={className}
      />
    </KintanaAuthProvider>
  );
}
