import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

/** @param {string} filePath */
function loadDotEnv(filePath) {
  if (!existsSync(filePath)) return;
  const text = readFileSync(filePath, "utf8");
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (!(key in process.env) || !process.env[key]?.trim()) {
      process.env[key] = value;
    }
  }
}

for (const file of [".env", ".env.local", ".dev.vars"]) {
  loadDotEnv(resolve(process.cwd(), file));
}

const key = process.env.PUBLIC_KINTANA_API_KEY?.trim();
const baseUrl = process.env.PUBLIC_KINTANA_BASE_URL?.trim();

if (!key || !baseUrl) {
  console.error("\n[Kintana build] Missing required variables at build time.\n");
  if (!key) console.error("  - PUBLIC_KINTANA_API_KEY is empty");
  if (!baseUrl) console.error("  - PUBLIC_KINTANA_BASE_URL is empty");
  console.error(
    "\nAdd PUBLIC_KINTANA_API_KEY and PUBLIC_KINTANA_BASE_URL in Cloudflare Pages → Environment variables (or your local `.env`), then redeploy.\n",
  );
  process.exit(1);
}

console.log("[Kintana build] API key and base URL present.");
