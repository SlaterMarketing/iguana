/**
 * End to end: actually reserve a seat, the way a person does, and look at every page on the way.
 *
 *   node tests/reserve-flow.mjs                           against production
 *   node tests/reserve-flow.mjs --base http://127.0.0.1:4321
 *   node tests/reserve-flow.mjs --lang en --night en
 *
 * This is the only check that proves the thing the ads are paying for actually works: it opens the lander a
 * Facebook click lands on, types into the checkout iframe, presses the button, follows the redirect the widget
 * posts to the parent page, and then reads the ticket, the QR code and the invite off the order page.
 *
 * Everything else in this repo asserts a part. A page can return 200, a pixel can fire, a test can pass, and
 * the button can still be attached to nothing: an earlier version of the invite lived in a template block the
 * base did not define and rendered silently as an empty string.
 *
 * 🚨 It creates a REAL reservation, which takes a seat, emails the customer and alerts hello@. Against
 * production, delete it afterwards; the script prints the order id and the exact command.
 */

import { mkdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { chromium } from "playwright";

const args = process.argv.slice(2);
const argOf = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};

const BASE = argOf("--base", "https://iguanacomedy.com").replace(/\/$/, "");
const LANG = argOf("--lang", "es");
const NIGHT = argOf("--night", "es");
const OUT = path.resolve(argOf("--out", "build/reserve-flow"));
const EMAIL = argOf("--email", `e2e-seat-${Date.now()}@iguanacomedy.com`);

const LANDER = { es: "/es/open-mic/", en: "/en/open-mic/" }[LANG];
const WORDS = {
  es: { reserve: /reserva|reservar/i, invite: /vienes con alguien/i, ticket: /boleto/i },
  en: { reserve: /reserve/i, invite: /bringing someone/i, ticket: /ticket/i },
}[LANG];

const failures = [];
const note = (ok, message) => {
  console.log(`${ok ? "  ok  " : "  FAIL"} ${message}`);
  if (!ok) failures.push(message);
};

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
  locale: LANG === "es" ? "es-MX" : "en-US",
});
const page = await context.newPage();
const consoleErrors = [];
page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));

let orderUrl = "";
try {
  // 1. The page the ad click lands on.
  const url = `${BASE}${LANDER}?night=${NIGHT}&fbclid=e2e-reserve`;
  console.log(`\nreserving at ${url}\n  as ${EMAIL}\n`);
  const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
  note(response?.status() === 200, `lander returns 200 (got ${response?.status()})`);
  await page.waitForSelector("iframe", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(3500);
  await page.screenshot({ path: path.join(OUT, "1-lander.png") });

  const frame = page.frames().find((f) => f.url().includes("/embed/event/"));
  note(Boolean(frame), "the checkout iframe loaded");
  if (!frame) throw new Error("no checkout iframe; nothing to reserve");

  // 2. Fill it in the way a person does, rather than posting JSON at the API.
  await frame.locator('input[name="name"]').fill("E2E Probe");
  await frame.locator('input[name="email"]').fill(EMAIL);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(OUT, "2-filled.png") });

  const button = frame.locator('button[type="submit"]');
  const label = (await button.innerText()).trim();
  note(WORDS.reserve.test(label), `the button says what it does ("${label.split("\n")[0]}")`);

  // 3. Press it, and follow the redirect the widget posts up to the parent page.
  await Promise.all([
    page.waitForURL(/\/orders\//, { timeout: 45000 }).catch(() => {}),
    button.click(),
  ]);
  await page.waitForTimeout(3000);
  orderUrl = page.url();
  note(/\/orders\//.test(orderUrl), `it lands on the order page (${orderUrl.slice(0, 64)})`);
  await page.screenshot({ path: path.join(OUT, "3-order.png"), fullPage: true });

  // 4. Read what the person actually got.
  const body = await page.locator("body").innerText();
  note(WORDS.ticket.test(body), "the order page shows a ticket");
  const qr = await page.locator("[data-qr] img, [data-qr] canvas").count();
  note(qr >= 1, `the QR code rendered (${qr} found)`);
  note(WORDS.invite.test(body), "the invite is on the page");

  const whatsapp = await page.locator('a[href^="https://wa.me/"]').first().getAttribute("href").catch(() => null);
  note(Boolean(whatsapp), "the WhatsApp invite link is there");
  if (whatsapp) {
    const shared = decodeURIComponent(whatsapp);
    note(shared.includes("/open-mic/"), "the shared link points at the open mic lander");
    note(shared.includes("ref=share"), "the shared link is marked as a share, so it can be told from ad traffic");
    note(shared.includes(`night=${NIGHT}`), `the shared link pins this night (night=${NIGHT})`);
  }
  const copy = await page.locator("#copy-invite").count();
  note(copy === 1, "the copy-link button is on the page");
  // The button is only real if its script actually rendered; an earlier version sat in a block that did not exist.
  note(/navigator\.share/.test(await page.content()), "and its script is on the page, not silently dropped");
} finally {
  if (consoleErrors.length) console.log(`\n  console errors: ${consoleErrors.slice(0, 3).join(" | ").slice(0, 200)}`);
  await context.close();
  await browser.close();
}

console.log(`\nscreenshots in ${OUT}`);
if (orderUrl) {
  console.log("\n🚨 this created a REAL reservation. On production, remove it with:");
  console.log(`   Order.objects.filter(customer_email='${EMAIL}').delete()`);
}
console.log(`\n${failures.length ? `${failures.length} check(s) FAILED` : "every check passed"} against ${BASE}`);
if (failures.length) {
  for (const f of failures) console.log(`  - ${f}`);
  process.exit(1);
}
