/**
 * A paid show, end to end, in a real browser: the event page in both languages, the listings, and the checkout
 * as far as Stripe will take it without a real card.
 *
 *   node tests/show-e2e.mjs --slug manu-rejon-playa-del-carmen --price 250 --capacity 75
 *   node tests/show-e2e.mjs --slug <slug> --base http://127.0.0.1:4321
 *
 * Pages: 200, title, poster drawn, Spanish and English descriptions, the price, the lineup clip served, no
 * horizontal overflow at 320 and 390, no console errors. Listings: the show is linked from /es/eventos/ and
 * /en/events/.
 *
 * Checkout: the ticket row and price, no pay-at-the-door wording, + raises the total, the card form draws, and
 * paying with Stripe's test card 4242 is REFUSED by the live account. That refusal is the proof the live keys
 * and the PaymentIntent work without spending anybody's money. Against a test-mode account it would succeed
 * and leave a real order; delete it afterwards either way (the script prints the email to look for).
 *
 * 🚨 The checkout's "engaged" beacon is BLOCKED here. It sends InitiateCheckout with the night's price to Meta,
 * and a paid show's ad set optimises on exactly that (value above 0), so a test run would teach the campaign
 * that the test suite is a buyer. Orders use an e2e- address, which ad_reporting already skips.
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
const SLUG = argOf("--slug", "");
const PRICE = Number(argOf("--price", "0"));
const CAPACITY = Number(argOf("--capacity", "0"));
const OUT = path.resolve(argOf("--out", "build/show-e2e"));
const EMAIL = argOf("--email", `e2e-show-${Date.now()}@iguanacomedy.com`);
if (!SLUG || !PRICE) {
  console.log("usage: node tests/show-e2e.mjs --slug <event slug> --price <MXN> [--capacity N]");
  process.exit(2);
}

const failures = [];
const note = (ok, message) => {
  console.log(`${ok ? "  ok  " : "  FAIL"} ${message}`);
  if (!ok) failures.push(message);
};
const money = (n) => `$${n.toFixed(2)}`;

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();

async function newPage(width, locale) {
  const context = await browser.newContext({
    viewport: { width, height: 844 },
    isMobile: width < 500,
    hasTouch: width < 500,
    locale,
  });
  await context.route("**/api/checkout/*/engaged", (route) => route.fulfill({ status: 204, body: "" }));
  const page = await context.newPage();
  page.errors = [];
  page.on("console", (m) => m.type() === "error" && page.errors.push(m.text()));
  page.on("pageerror", (e) => page.errors.push(String(e)));
  return page;
}

const PAGES = {
  es: { url: `/es/eventos/${SLUG}/`, listing: "/es/eventos/", locale: "es-MX", buy: /pagar/i },
  en: { url: `/en/events/${SLUG}/`, listing: "/en/events/", locale: "en-US", buy: /pay/i },
};

for (const [lang, spec] of Object.entries(PAGES)) {
  console.log(`\n${lang}: ${spec.url}`);
  for (const width of [320, 390]) {
    const page = await newPage(width, spec.locale);
    const response = await page.goto(BASE + spec.url, { waitUntil: "load" });
    note(response.status() === 200, `${width}px status ${response.status()}`);
    await page.waitForTimeout(1500);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    note(overflow <= 1, `${width}px no horizontal overflow (${overflow}px)`);
    if (width === 390) {
      const title = await page.title();
      note(/Manu|Rej/i.test(title) || title.length > 0, `title: ${title}`);
      const body = await page.locator("body").innerText();
      note(body.includes(String(PRICE)), `page states the price ${PRICE}`);
      note(!/puerta|at the door/i.test(body.replace(/puertas|doors/gi, "")), "no pay-at-the-door wording");
      const posters = await page.evaluate(() =>
        [...document.images].filter((i) => /media\/events\//.test(i.currentSrc || i.src))
          .map((i) => ({ src: i.currentSrc || i.src, ok: i.complete && i.naturalWidth > 0 })));
      note(posters.length > 0 && posters.some((p) => p.ok), `poster drawn (${posters.length} poster image(s))`);
      const ld = await page.evaluate(() => [...document.querySelectorAll('script[type="application/ld+json"]')]
        .map((s) => s.textContent).join(" "));
      note(ld.includes(`${PRICE}`) && /startDate/.test(ld), "JSON-LD carries the date and price");
      const reels = await page.evaluate(() =>
        [...document.querySelectorAll("video source, video[src]")].map((v) => v.src || v.getAttribute("src")));
      for (const reel of reels.filter(Boolean)) {
        const head = await page.request.fetch(reel, { method: "HEAD" });
        note(head.status() === 200, `clip served: ${reel} (${head.status()})`);
      }
      note(reels.length > 0, `the page carries a clip of the act (${reels.length})`);
      await page.screenshot({ path: path.join(OUT, `${lang}-${width}-top.png`) });
      const real = page.errors.filter((e) => !/stripe|favicon|facebook|fbevents|ERR_BLOCKED/i.test(e));
      note(real.length === 0, `no console errors${real.length ? `: ${real.slice(0, 3).join(" | ")}` : ""}`);
    }
    await page.context().close();
  }

  const listing = await newPage(390, spec.locale);
  await listing.goto(BASE + spec.listing, { waitUntil: "load" });
  const linked = await listing.locator(`a[href*="${SLUG}"]`).count();
  note(linked > 0, `${spec.listing} links the show (${linked} link(s))`);
  await listing.context().close();
}

console.log("\ncheckout (es):");
{
  const page = await newPage(390, "es-MX");
  await page.goto(BASE + PAGES.es.url, { waitUntil: "load" });
  const holder = await page.waitForSelector("iframe[src*='/embed/event/']", { timeout: 30000 });
  await holder.scrollIntoViewIfNeeded();
  const frame = await holder.contentFrame();
  await frame.waitForSelector("#types button, #types .type", { timeout: 30000 });
  await page.waitForTimeout(1500);
  let text = await frame.locator("body").innerText();
  note(text.includes(money(PRICE)), `ticket row shows ${money(PRICE)} MXN`);
  note(!/paga en la puerta|pay at the door/i.test(text), "no pay-at-the-door option");
  note(!/miembro|member/i.test(text), "no member pricing offered");

  const plus = frame.locator("#types button").last();
  await plus.click();
  await page.waitForTimeout(1500);
  text = await frame.locator("body").innerText();
  note(text.includes(money(PRICE * 2)), `+ raises the total to ${money(PRICE * 2)}`);
  const minus = frame.locator("#types button").first();
  await minus.click();
  await page.waitForTimeout(1500);

  await frame.fill("input[name=name]", "E2E prueba, ignore");
  await frame.fill("input[name=email]", EMAIL);
  const stripeFrame = await frame.waitForSelector("#payment-element iframe", { timeout: 45000 }).catch(() => null);
  note(Boolean(stripeFrame), "Stripe card form drawn");
  if (stripeFrame) {
    const card = await stripeFrame.contentFrame();
    await card.waitForSelector("input[name=number]", { timeout: 30000 });
    await card.fill("input[name=number]", "4242424242424242");
    await card.fill("input[name=expiry]", "12 / 34");
    await card.fill("input[name=cvc]", "123");
    const postal = card.locator("input[name=postalCode]");
    if (await postal.count()) await postal.fill("77710");
    await page.screenshot({ path: path.join(OUT, "checkout-filled.png"), fullPage: true });
    const button = frame.locator("#submit");
    note((await button.innerText()).includes(money(PRICE)), `button says ${await button.innerText()}`);
    const started = page.waitForResponse((r) => /\/api\/checkout\/[^/]+\/start/.test(r.url()) || /checkout.*start/.test(r.url()),
      { timeout: 30000 }).catch(() => null);
    await button.click();
    const response = await started;
    if (response) {
      const body = await response.json().catch(() => ({}));
      note(response.status() === 200 && Boolean(body.clientSecret), `checkout made a live PaymentIntent (order ${body.orderId || "?"})`);
    } else {
      note(false, "checkout start request seen");
    }
    const error = frame.locator("#error");
    await error.waitFor({ state: "visible", timeout: 45000 }).catch(() => null);
    const said = (await error.isVisible()) ? await error.innerText() : "";
    const url = page.url();
    note(Boolean(said) && !/orders\//.test(url), `live Stripe refused the test card: "${said.slice(0, 120)}"`);
    await page.screenshot({ path: path.join(OUT, "checkout-refused.png"), fullPage: true });
  }
  await page.context().close();
}

await browser.close();
console.log(`\nprobe email: ${EMAIL} (delete its pending order on the server)`);
console.log(`screenshots: ${OUT}`);
console.log(failures.length ? `\n${failures.length} failure(s)` : "\nall passed");
process.exit(failures.length ? 1 : 0);
