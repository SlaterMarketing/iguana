import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const root = existsSync("/app/package.json") ? resolve("/app") : process.cwd();

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

for (const file of [resolve(root, ".env"), resolve(process.cwd(), ".env")]) {
  loadDotEnv(file);
}

const publicKeys = Object.keys(process.env).filter((key) => key.startsWith("PUBLIC_"));
const envLines = publicKeys.sort().map((key) => `${key}=${process.env[key] ?? ""}`);
writeFileSync(resolve(root, ".env"), `${envLines.join("\n")}\n`, "utf8");

const required = ["PUBLIC_KINTANA_API_KEY", "PUBLIC_KINTANA_BASE_URL", "PUBLIC_SITE_URL"];
for (const key of required) {
  const value = process.env[key]?.trim();
  console.log(`[iguana] ${key}: ${value ? `set (${value.length} chars)` : "MISSING"}`);
}
