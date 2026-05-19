import { createKintanaClient } from "@kintana/sdk";
import type { KintanaPublicFile } from "@kintana/sdk";

import type { SiteBrandOverrides } from "../content/site-assets";
import { SITE_BRAND_FILE_ALIASES } from "../content/site-assets";

const TTL_MS = 5 * 60 * 1000;

/** Last resolved overrides — may be `{}` legitimately — always TTL-gated refresh. */
let expiresAtMs = 0;
let cached: SiteBrandOverrides = {};

/** Lowercase basename without trailing extension — used to match curated names against files from Kintana. */
export function normalizeStem(fileName: string): string {
  const base = fileName.trim().replace(/\\/g, "/").split("/").pop() ?? fileName.trim();
  return base.replace(/\.[a-z0-9]{1,8}$/i, "").toLowerCase();
}

export function urlsByStem(files: readonly KintanaPublicFile[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const f of files) {
    const stem = normalizeStem(f.name);
    if (!map.has(stem)) map.set(stem, f.url);
  }
  return map;
}

export function overridesFromPublicFiles(files: readonly KintanaPublicFile[]): SiteBrandOverrides {
  const byStem = urlsByStem(files);
  const out: SiteBrandOverrides = {};
  for (const { key, candidates } of SITE_BRAND_FILE_ALIASES) {
    for (const cand of candidates) {
      const url = byStem.get(cand.toLowerCase());
      if (url) {
        out[key] = url;
        break;
      }
    }
  }
  return out;
}

/**
 * Resolved link-share files for brand imagery (TTL cache). Runs server-side only.
 */
export async function fetchCachedBrandOverrides(apiKey: string, baseUrl: string): Promise<SiteBrandOverrides> {
  const now = Date.now();
  if (now < expiresAtMs) return cached;

  cached = {};

  try {
    const trimmedKey = apiKey.trim();
    const trimmedBase = baseUrl.trim();
    if (!trimmedKey || !trimmedBase) {
      expiresAtMs = now + 30_000;
      return cached;
    }

    const client = createKintanaClient({ apiKey: trimmedKey, baseUrl: trimmedBase });
    const files = await client.listFiles({ limit: 100 });
    cached = overridesFromPublicFiles(files);
  } catch {
    cached = {};
  }

  expiresAtMs = Date.now() + TTL_MS;
  return cached;
}
