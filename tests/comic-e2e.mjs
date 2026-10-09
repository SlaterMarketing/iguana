/**
 * The comedian upload page, /comic/, in a real browser.
 *
 *   node tests/comic-e2e.mjs                                  layout only, against production
 *   node tests/comic-e2e.mjs --base http://127.0.0.1:8123     against a local Django (runserver)
 *   node tests/comic-e2e.mjs --submit                         also send ONE submission with tiny files
 *   node tests/comic-e2e.mjs --submit --email postmaster@iguanacomedy.com   ...and read the receipt in iguana-mail
 *
 * Layout: both languages at 320, 360, 390 and 1280 wide, asserting no horizontal page overflow and no input
 * wider than its fieldset. --submit fills the form as "E2E prueba, ignore" with an e2e- address at our own
 * domain, a generated JPEG and a 2 second MP4 (ffmpeg), and waits for the thank-you page. Delete the row
 * afterwards on the server: `manage.py comic_submission <id> --delete`.
 * Screenshots land in build/e2e/.
 */

import { execFileSync } from "node:child_process";
import { mkdir, mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const args = process.argv.slice(2);
const argOf = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const BASE = argOf("--base", "https://iguanacomedy.com").replace(/\/$/, "");
const OUT = path.resolve(argOf("--out", "build/e2e"));
const SUBMIT = args.includes("--submit");
// A role address that delivers to the server's own inbox (postmaster@) proves the comedian's receipt arrives.
const EMAIL = argOf("--email", "e2e-comic@iguanacomedy.com");
const WIDTHS = [320, 360, 390, 1280];

const failures = [];
const fail = (msg) => {
  failures.push(msg);
  console.log(`FAIL ${msg}`);
};

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();

for (const lang of ["es", "en"]) {
  for (const width of WIDTHS) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, isMobile: width < 500 });
    const res = await page.goto(`${BASE}/comic/?lang=${lang}`);
    if (res.status() !== 200) fail(`${lang} ${width}: status ${res.status()}`);
    const heading = (await page.textContent("h1")) || "";
    const expected = lang === "es" ? "quieres un show" : "want a show";
    if (!heading.toLowerCase().includes(expected)) fail(`${lang} ${width}: heading "${heading}"`);
    const layout = await page.evaluate(() => {
      const doc = document.documentElement;
      const wide = [];
      document.querySelectorAll("input:not([type=hidden]):not([tabindex='-1']), textarea, button, legend").forEach((el) => {
        const r = el.getBoundingClientRect();
        if (r.width && (r.right > doc.clientWidth + 1 || r.left < -1)) wide.push(`${el.tagName} ${el.name || ""} ${Math.round(r.right)}`);
        if (el.scrollWidth > el.clientWidth + 2 && el.tagName === "BUTTON") wide.push(`clipped ${el.textContent.trim()}`);
      });
      return { overflow: doc.scrollWidth - doc.clientWidth, wide };
    });
    if (layout.overflow > 0) fail(`${lang} ${width}: page overflows by ${layout.overflow}px`);
    for (const w of layout.wide) fail(`${lang} ${width}: ${w}`);
    await page.screenshot({ path: path.join(OUT, `comic-${lang}-${width}.png`), fullPage: true });
    await page.close();
    console.log(`ok ${lang} ${width}px`);
  }
}

if (SUBMIT) {
  const dir = await mkdtemp(path.join(os.tmpdir(), "comic-e2e-"));
  const jpg = path.join(dir, "e2e-photo.jpg");
  const mp4 = path.join(dir, "e2e-clip.mp4");
  execFileSync("ffmpeg", ["-v", "error", "-y", "-f", "lavfi", "-i", "color=c=green:s=640x800", "-frames:v", "1", jpg]);
  execFileSync("ffmpeg", ["-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
    "-pix_fmt", "yuv420p", mp4]);

  const page = await browser.newPage({ viewport: { width: 320, height: 800 }, isMobile: true });
  await page.goto(`${BASE}/comic/?lang=es`);
  await page.fill("input[name=name]", "E2E prueba, ignore");
  await page.fill("input[name=email]", EMAIL);
  await page.fill("input[name=home_city]", "Prueba automatizada");
  await page.check("input[name=lang_es]");
  await page.fill("textarea[name=bio]", "Envio de prueba automatizado, por favor ignorar.");
  await page.setInputFiles("input[name=photos]", jpg);
  await page.setInputFiles("input[name=clip_short]", mp4);
  const day = new Date(Date.now() + 40 * 86400000).toISOString().slice(0, 10);
  await page.fill("input[name=dates] >> nth=0", day);
  await page.click("#add-date");
  if ((await page.locator("input[name=dates]").count()) !== 4) fail("add another date did not add an input");
  await page.check("input[name=consent]");
  await Promise.all([page.waitForURL(/\/comic\/thanks\//, { timeout: 60000 }), page.click("#send")]);
  const thanks = (await page.textContent("h1")) || "";
  if (!thanks.toLowerCase().includes("gracias")) fail(`thank-you page says "${thanks}"`);
  await page.screenshot({ path: path.join(OUT, "comic-thanks-es-320.png"), fullPage: true });
  console.log(`submitted, landed on ${page.url()}`);
}

await browser.close();
if (failures.length) {
  console.log(`${failures.length} failure(s)`);
  process.exit(1);
}
console.log("all good");
