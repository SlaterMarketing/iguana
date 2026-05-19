import { defineMiddleware } from "astro:middleware";

import { fetchCachedBrandOverrides } from "./lib/kintana-files";
import { getKintanaEnv } from "./lib/kintana-env";

export const onRequest = defineMiddleware(async ({ locals }, next) => {
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
