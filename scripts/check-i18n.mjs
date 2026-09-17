// Fails the build when the Spanish site would silently show English. `t()` falls back to the English string for any
// key missing from `ui.es`, so a forgotten translation would otherwise ship with no error anywhere.
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { build } from "esbuild";

const dir = mkdtempSync(join(tmpdir(), "iguana-i18n-"));
try {
  const outfile = join(dir, "ui.mjs");
  await build({ entryPoints: [process.argv[2] ?? "src/i18n/ui.ts"], outfile, format: "esm", bundle: true, platform: "node", logLevel: "error" });
  const { ui } = await import(pathToFileURL(outfile).href);

  const slots = (text) => (String(text).match(/\{[A-Za-z0-9_]+\}/g) ?? []).sort().join(",");
  const problems = [];
  for (const [key, en] of Object.entries(ui.en)) {
    const es = ui.es[key];
    if (typeof es !== "string" || !es.trim()) problems.push(`missing Spanish: ${key}`);
    else if (slots(en) !== slots(es)) problems.push(`slots differ: ${key} (en ${slots(en)} / es ${slots(es)})`);
  }
  for (const key of Object.keys(ui.es)) {
    if (!(key in ui.en)) problems.push(`Spanish-only key (never used by t()): ${key}`);
  }
  const count = Object.keys(ui.en).length;
  // A check that read nothing would pass, so insist it actually saw the table.
  if (count < 100) problems.push(`only ${count} English keys found, so this check is not reading src/i18n/ui.ts`);

  if (problems.length) {
    console.error(`i18n check failed:\n  ${problems.join("\n  ")}`);
    process.exit(1);
  }
  console.log(`i18n check: ${count} keys, every one translated`);
} finally {
  rmSync(dir, { recursive: true, force: true });
}
