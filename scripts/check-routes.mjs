// Fails the build when a page's hreflang/language switcher would not point at its own translation. This broke once
// without any error: trailing slashes stopped every route but home from matching.
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { build } from "esbuild";

const CASES = [
  ["en", "/en/", "/es/"],
  ["en", "/en/events/", "/es/eventos/"],
  ["en", "/en/events/playa-del-carmen-2026-09-23/", "/es/eventos/playa-del-carmen-2026-09-23/"],
  ["en", "/en/events/improvincia/tickets/", "/es/eventos/improvincia/boletos/"],
  ["en", "/en/locations/cancun/", "/es/sedes/cancun/"],
  ["en", "/en/comedians/andre-de-freitas/", "/es/comediantes/andre-de-freitas/"],
  ["en", "/en/legal/privacy-policy/", "/es/legal/politica-de-privacidad/"],
  ["en", "/en/contact/", "/es/contacto/"],
  ["en", "/en/contact", "/es/contacto/"],
  ["es", "/es/eventos/playa-del-carmen-2026-09-22/", "/en/events/playa-del-carmen-2026-09-22/"],
  ["es", "/es/sedes/tulum/", "/en/locations/tulum/"],
  ["es", "/es/membresia/", "/en/membership/"],
  ["es", "/es/tienda/", "/en/store/"],
];

const dir = mkdtempSync(join(tmpdir(), "iguana-routes-"));
try {
  const outfile = join(dir, "routes.mjs");
  await build({ entryPoints: ["src/i18n/routes.ts"], outfile, format: "esm", bundle: true, platform: "node", logLevel: "error" });
  const { getAlternatePath } = await import(pathToFileURL(outfile).href);
  const failures = CASES.flatMap(([locale, path, expected]) => {
    const actual = getAlternatePath(locale, path);
    return actual === expected ? [] : [`${path} -> ${actual} (expected ${expected})`];
  });
  if (failures.length) {
    console.error(`route check failed:\n  ${failures.join("\n  ")}`);
    process.exit(1);
  }
  console.log(`route check: ${CASES.length} translated page pairs resolve`);
} finally {
  rmSync(dir, { recursive: true, force: true });
}
