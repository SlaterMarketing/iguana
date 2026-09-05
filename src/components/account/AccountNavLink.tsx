"use client";

import { useEffect, useState } from "react";
import { membershipPaths, readStoredAccessToken } from "../../lib/kintana-auth";
import type { Locale } from "../../i18n/routes";

type Props = {
  locale: Locale;
  loginLabel: string;
  accountLabel: string;
  className?: string;
  /** When set, click closes the mobile drawer (Header listens for this attribute). */
  closeMobileMenu?: boolean;
};

export function AccountNavLink({
  locale,
  loginLabel,
  accountLabel,
  className,
  closeMobileMenu,
}: Props) {
  const paths = membershipPaths(locale);
  const [href, setHref] = useState(paths.accountSignIn);
  const [label, setLabel] = useState(loginLabel);

  useEffect(() => {
    if (readStoredAccessToken()) {
      setHref(paths.account);
      setLabel(accountLabel);
    } else {
      setHref(paths.accountSignIn);
      setLabel(loginLabel);
    }
  }, [accountLabel, loginLabel, paths.account, paths.accountSignIn]);

  return (
    <a
      href={href}
      className={className}
      {...(closeMobileMenu ? { "data-mobile-menu-close": "" } : {})}
    >
      {label}
    </a>
  );
}
