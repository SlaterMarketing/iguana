import { existsSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(process.cwd(), "dist");
const required = [
  "_worker.js/index.js",
  "_routes.json",
  "en/comedy-for-everyone/index.html",
  "robots.txt",
];

const missing = required.filter((path) => !existsSync(resolve(root, path)));

if (missing.length) {
  console.error("\n[Cloudflare build] dist output is incomplete:\n");
  for (const path of missing) console.error(`  - dist/${path}`);
  console.error("\nCheck Pages build command/output directory and build logs.\n");
  process.exit(1);
}

console.log("[Cloudflare build] dist output looks valid.");
