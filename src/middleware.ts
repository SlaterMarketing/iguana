import { defineMiddleware } from "astro:middleware";

import { fetchCachedBrandOverrides } from "./lib/kintana-files";
import { getKintanaEnv } from "./lib/kintana-env";
import { legacyRedirectTarget } from "./lib/legacy-paths";
import { LOCALE_PREFERENCE_COOKIE, resolveRootLocale } from "./lib/locale-preference";

export const onRequest = defineMiddleware(async (context, next) => {
  const { pathname } = context.url;
  if (pathname === "/" || pathname === "") {
    const locale = resolveRootLocale({
      preferenceCookie: context.cookies.get(LOCALE_PREFERENCE_COOKIE)?.value,
      acceptLanguage: context.request.headers.get("Accept-Language"),
    });
    return context.redirect(`/${locale}/`, 302);
  }

  if (pathname === "/es") {
    return context.redirect("/es/", 302);
  }

  // The menu QR codes are printed once and stuck to a table, so they carry no locale: `/menu/7/` picks a
  // language the same way `/` does and keeps working for a Spanish local and an English tourist at the same
  // table. Re-printing a hundred stickers to change a language prefix is not a thing anyone should have to do.
  const unprefixedMenu = /^\/menu(?:\/(?:qr|[0-9]{1,3}(?:\/qr)?)?)?\/?$/.exec(pathname);
  if (unprefixedMenu) {
    const locale = resolveRootLocale({
      preferenceCookie: context.cookies.get(LOCALE_PREFERENCE_COOKIE)?.value,
      acceptLanguage: context.request.headers.get("Accept-Language"),
    });
    const tail = pathname.endsWith("/") ? pathname : `${pathname}/`;
    return context.redirect(`/${locale}${tail}${context.url.search}`, 302);
  }

  const legacyTarget = legacyRedirectTarget(pathname);
  if (legacyTarget) {
    return context.redirect(legacyTarget + context.url.search, 301);
  }

  const { locals } = context;
  const runtimeEnv = locals.runtime?.env as Record<string, string | undefined> | undefined;
  const { apiKey, baseUrl } = getKintanaEnv(runtimeEnv);
  if (apiKey && baseUrl) {
    try {
      locals.brandOverrides = await fetchCachedBrandOverrides(apiKey, baseUrl);
    } catch {
      locals.brandOverrides = {};
    }
  } else {
    locals.brandOverrides = {};
  }
  return next();
});
