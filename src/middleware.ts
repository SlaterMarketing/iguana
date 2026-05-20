import { defineMiddleware } from "astro:middleware";

import { fetchCachedBrandOverrides } from "./lib/kintana-files";
import { getKintanaEnv } from "./lib/kintana-env";
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

  const { locals } = context;
  const { apiKey, baseUrl } = getKintanaEnv();
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
