/**
 * The staff console at phone widths, measured rather than eyeballed.
 *
 * These pages are read one-handed, in a dark room, by somebody holding a tray, and they are the only pages
 * here that nobody outside the building ever sees, so a layout fault on them can sit for weeks. Two things are
 * checked, and the second is the one that hides:
 *
 *   1. The PAGE overflowing its viewport, which shows up as horizontal scroll.
 *   2. An element clipped INSIDE its own box, which does not move the page at all. The first floor nav gave
 *      each pill `flex: 1 1 0` with a `min-width`, and the result was a pill narrower than its own uppercase
 *      label: "INVENTARIO" was cut off at every width tested while the page looked fine at 390.
 *
 * Plus tap targets under 40px, because a 15px-tall link is a fine target for a mouse and a bad one for a thumb.
 *
 *   node tests/mobile-sweep.mjs --staff mesero --pass <floor password>
 */
import { chromium } from "playwright";

const BASE = "https://iguanacomedy.com";
const WIDTHS = [320, 360, 390, 430];
const PAGES = [["/mesas/", "Mesas"], ["/mesas/carta/", "Carta"],
               ["/mesas/inventario/", "Inventario"], ["/mesas/reservas/", "Reservas"]];
const USER = process.argv[process.argv.indexOf("--staff") + 1];
const PASS = process.argv[process.argv.indexOf("--pass") + 1];

if (!USER || !PASS) {
  console.log("usage: node tests/mobile-sweep.mjs --staff mesero --pass <floor password>");
  process.exit(2);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "es-MX" });
const page = await ctx.newPage();
await page.goto(`${BASE}/mesas/entrar/`, { waitUntil: "domcontentloaded" });
await page.fill('input[name="username"]', USER);
await page.fill('input[name="password"]', PASS);
await page.click('button[type="submit"]');
await page.waitForTimeout(2500);
if (page.url().includes("entrar")) {
  console.log("FAIL  could not sign in to the floor console");
  process.exit(1);
}

let failures = 0;
for (const width of WIDTHS) {
  await page.setViewportSize({ width, height: 844 });
  for (const [path, label] of PAGES) {
    await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1200);
    const found = await page.evaluate((vw) => {
      const name = (el) => el.tagName.toLowerCase()
        + (typeof el.className === "string" && el.className.trim() ? "." + el.className.trim().split(/\s+/)[0] : "");
      const overflow = Math.max(0, document.documentElement.scrollWidth - vw);
      const clipped = [];
      const offscreen = [];
      for (const el of document.querySelectorAll("body *")) {
        const box = el.getBoundingClientRect();
        if (box.width === 0 && box.height === 0) continue;
        if (Math.round(box.right - vw) > 1 || Math.round(box.left) < -1) {
          offscreen.push(`${name(el)} ${Math.round(box.left)}..${Math.round(box.right)} of ${vw}`);
        }
        const style = getComputedStyle(el);
        if (el.scrollWidth - el.clientWidth > 2 && !["auto", "scroll"].includes(style.overflowX)) {
          clipped.push(`${name(el)} needs ${el.scrollWidth} has ${el.clientWidth}`);
        }
      }
      const small = [];
      for (const el of document.querySelectorAll("button, a, input, select, summary")) {
        const box = el.getBoundingClientRect();
        if (!(box.width || box.height)) continue;
        // A checkbox is always about 26px, and measuring the box alone reports a fault that is not there: a
        // <label> wrapping it is itself a target, so the row is what the thumb actually hits. Measure the
        // label when there is one, or this check demands a giant checkbox and gets a worse page.
        const label = (el.tagName === "INPUT" && ["checkbox", "radio"].includes(el.type)) ? el.closest("label") : null;
        const target = label ? label.getBoundingClientRect() : box;
        if (target.height < 40) {
          small.push(`${name(el)} ${Math.round(target.width)}x${Math.round(target.height)} "${(el.textContent || "").trim().slice(0, 16)}"`);
        }
      }
      return {
        overflow,
        clipped: [...new Set(clipped)].slice(0, 6),
        offscreen: [...new Set(offscreen)].slice(0, 6),
        small: [...new Set(small)].slice(0, 6),
      };
    }, width);

    const problems = (found.overflow > 1 ? 1 : 0) + found.clipped.length + found.offscreen.length + found.small.length;
    if (problems) failures += 1;
    console.log(`${problems ? "FAIL" : "ok  "}  ${String(width).padEnd(4)} ${label.padEnd(11)}`
      + `${found.overflow > 1 ? ` page overflows ${found.overflow}px` : ""}`);
    for (const line of found.offscreen) console.log(`        offscreen: ${line}`);
    for (const line of found.clipped) console.log(`        clipped:   ${line}`);
    for (const line of found.small) console.log(`        small tap: ${line}`);
  }
}

await browser.close();
console.log(`\n${WIDTHS.length * PAGES.length - failures}/${WIDTHS.length * PAGES.length} page/width combinations clean`);
process.exit(failures ? 1 : 0);
