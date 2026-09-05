"use client";

import { useEffect, useState } from "react";
import { KintanaAuthProvider, useKintanaAuth } from "@kintana/sdk/react";
import { membershipPaths } from "../../lib/kintana-auth";
import type { Locale } from "../../i18n/routes";

type Props = {
  apiKey: string;
  baseUrl: string;
  locale: Locale;
  token: string;
};

const copy = {
  en: {
    invalid: "That sign-in link is invalid or has expired.",
    tryAgain: "Try signing in again",
    signingIn: "Signing you in…",
  },
  es: {
    invalid: "Ese enlace de acceso no es válido o ha vencido.",
    tryAgain: "Intenta iniciar sesión de nuevo",
    signingIn: "Entrando…",
  },
} as const;

function VerifyTokenInner({ token, locale }: { token: string; locale: Locale }) {
  const t = copy[locale];
  const paths = membershipPaths(locale);
  const { verifyToken } = useKintanaAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    void verifyToken(token)
      .then(() => {
        if (alive) window.location.assign(paths.account);
      })
      .catch((err: unknown) => {
        if (alive) {
          setError(err instanceof Error ? err.message : t.invalid);
        }
      });
    return () => {
      alive = false;
    };
  }, [token, verifyToken, paths.account, t.invalid]);

  if (error) {
    return (
      <div>
        <p className="form-error">{error}</p>
        <a href={paths.accountSignIn} className="account-auth-switch-link">
          {t.tryAgain}
        </a>
      </div>
    );
  }

  return <p className="account-status-copy">{t.signingIn}</p>;
}

export function VerifyTokenHandler({ apiKey, baseUrl, locale, token }: Props) {
  return (
    <KintanaAuthProvider apiKey={apiKey} baseUrl={baseUrl}>
      <VerifyTokenInner token={token} locale={locale} />
    </KintanaAuthProvider>
  );
}
