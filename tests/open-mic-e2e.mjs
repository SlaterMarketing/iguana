/**
 * End to end check of the page every open mic ad points at, with screenshots as the evidence.
 *
 *   node tests/open-mic-e2e.mjs                          against production
 *   node tests/open-mic-e2e.mjs --base http://127.0.0.1:4321   against a local build
 *
 * It exists because a 502 inside the checkout iframe is invisible to everything else we check. The page itself
 * answers 200, the API answers 200 a second later, and the only thing that ever saw the failure was a person
 * looking at the screen. So this drives a real browser, waits for the iframe to load, and reads what is actually
 * rendered inside it.
 *
 * What it asserts, per language:
 *   - the page loads and the Meta pixel initialises
 *   - both checkout iframes load and contain a real reserve button, not an nginx error page
 *   - the price, the date and the start of the checkout are on the first screen, at a 1280x800
 *     laptop and on a 390x844 phone, with the reserve button within one flick of it
 *   - the later dates are offered, and the email fallback is present
 * Screenshots land in build/e2e/ whether it passes or fails, because a failure is the one you want to look at.
 */

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const args = process.argv.slice(2);
const argOf = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};

const BASE = argOf("--base", "https://iguanacomedy.com").replace(/\/$/, "");
const OUT = path.resolve(argOf("--out", "build/e2e"));
const VIEWPORTS = [
  { name: "laptop", width: 1280, height: 800 },
  { name: "phone", width: 390, height: 844, isMobile: true },
];
const PAGES = [
  // The button says "Pay 50 MXN / 1 ticket" for a paid seat and "Reserve 1 seat" for a pay-at-the-door one, so
  // both count: what matters is that it is a real call to action carrying the price, not a bare plus sign.
  { lang: "en", path: "/en/open-mic/", reserve: /reserve|pay/i, later: /book a later night/i, price: /50/ },
  { lang: "es", path: "/es/open-mic/", reserve: /reservar|pagar/i, later: /reserva una más adelante/i, price: /50/ },
];

// nginx and gunicorn error bodies, which is exactly what an ad click found inside the checkout on 2026-09-20.
const ERROR_BODY = /502 Bad Gateway|504 Gateway|503 Service|Bad Gateway|nginx\/|Internal Server Error/i;

const failures = [];
const note = (ok, message) => {
  console.log(`${ok ? "  ok  " : "  FAIL"} ${message}`);
  if (!ok) failures.push(message);
};

async function launch() {
  let chromium;
  try {
    ({ chromium } = await import("playwright"));
  } catch {
    try {
      ({ chromium } = await import("playwright-core"));
    } catch {
      console.error("This needs playwright. Install it with: npm i -D playwright");
      process.exit(2);
    }
  }
  return chromium.launch();
}

async function checkPage(browser, entry, viewport) {
  const label = `${entry.lang}-${viewport.name}`;
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    isMobile: Boolean(viewport.isMobile),
    hasTouch: Boolean(viewport.isMobile),
    // Ad traffic arrives with a click id, so test the URL people actually land on.
    locale: entry.lang === "es" ? "es-MX" : "en-US",
  });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));

  const url = `${BASE}${entry.path}?fbclid=e2e-check`;
  console.log(`\n${label}: ${url}`);
  const response = await page.goto(url, { waitUntil: "networkidle", timeout: 45000 });
  note(response?.status() === 200, `page returns 200 (got ${response?.status()})`);

  // The checkout arrives in an iframe injected by k.js, so give it time to appear and settle.
  await page.waitForTimeout(3500);

  const frames = page.frames().filter((f) => f.url().includes("/embed/event/"));
  note(frames.length >= 1, `checkout iframe present (found ${frames.length})`);

  for (const [index, frame] of frames.entries()) {
    let text = "";
    try {
      text = (await frame.locator("body").innerText({ timeout: 10000 })).trim();
    } catch (err) {
      note(false, `iframe ${index + 1} body unreadable: ${err.message.split("\n")[0]}`);
      continue;
    }
    // This is the check that would have caught the 502: the page was fine, the iframe was not.
    note(!ERROR_BODY.test(text), `iframe ${index + 1} is the checkout, not a server error page`);
    // Specifically the submit button, not the quantity stepper. Measuring "the first button" once reported a
    // pass on a card whose only visible control was a plus sign and the words "choose how many with +".
    const reserve = frame.locator("button[type=submit], form button:not(.qty button)");
    const button = await reserve.count();
    note(button >= 1, `iframe ${index + 1} shows a reserve button without touching anything (found ${button})`);
    if (button) {
      const label = (await reserve.first().innerText().catch(() => "")).trim();
      note(entry.reserve.test(label), `reserve button reads like a reserve button ("${label}")`);
    }
    if (ERROR_BODY.test(text)) console.log(`        got: ${text.slice(0, 120).replace(/\s+/g, " ")}`);
  }

  // What "above the fold" can honestly mean here.
  //
  // The checkout asks for a name and an email before it can take a booking, so roughly 300px of form sits
  // between the price and the button. On a 390x844 phone the button therefore cannot share the first screen
  // with the club's header, the page heading and the date. Demanding it would only be satisfied by deleting
  // something a buyer needs.
  //
  // So the fold test is on the OFFER, which is what the click was bought for: the price and the date and the
  // start of the checkout have to be on the first screen, with the button one short flick away. An earlier
  // version asserted "the first button is above the fold" and passed happily on a card whose only visible
  // control was a plus sign next to the word zero.
  const iframeBox = frames.length
    ? await page.locator("iframe").first().boundingBox().catch(() => null)
    : null;
  note(iframeBox !== null && iframeBox.y < viewport.height,
    `the checkout starts on the first screen (${iframeBox ? Math.round(iframeBox.y) : "?"}px vs ${viewport.height}px)`);

  const priceAbove = await page.evaluate((fold) => {
    const nodes = [...document.querySelectorAll("p, span")];
    return nodes.some((n) => /\b50\b/.test(n.textContent || "") && n.getBoundingClientRect().top < fold);
  }, viewport.height);
  note(priceAbove, "the price is on the first screen");

  const firstButton = frames.length
    ? await frames[0].locator("button[type=submit], form button:not(.qty button)").first()
        .boundingBox().catch(() => null)
    : null;
  const buttonTop = firstButton && iframeBox ? iframeBox.y + firstButton.y : null;
  if (buttonTop === null) {
    note(false, "could not locate the reserve button to measure the fold");
  } else {
    note(buttonTop < viewport.height * 1.5,
      `reserve button is within one flick (${Math.round(buttonTop)}px vs ${Math.round(viewport.height * 1.5)}px)`);
  }

  const body = await page.locator("body").innerText();
  note(entry.later.test(body), "later dates are offered");
  note(/fbq/.test(await page.content()), "Meta pixel is on the page");
  const newsletter = await page.locator("form[data-newsletter]").count();
  note(newsletter >= 1, `email fallback is present (found ${newsletter})`);

  const shot = path.join(OUT, `${label}.png`);
  await page.screenshot({ path: shot, fullPage: false });
  const full = path.join(OUT, `${label}-full.png`);
  await page.screenshot({ path: full, fullPage: true });
  console.log(`        screenshots: ${shot} and ${full}`);

  if (consoleErrors.length) {
    console.log(`        console errors: ${consoleErrors.slice(0, 3).join(" | ").slice(0, 240)}`);
  }
  await context.close();
  return { label, shot, full, consoleErrors };
}

const browser = await launch();
await mkdir(OUT, { recursive: true });
const results = [];
try {
  for (const entry of PAGES) {
    for (const viewport of VIEWPORTS) {
      results.push(await checkPage(browser, entry, viewport));
    }
  }
} finally {
  await browser.close();
}

await writeFile(path.join(OUT, "summary.json"),
  JSON.stringify({ base: BASE, at: new Date().toISOString(), failures, results }, null, 2));

console.log(`\n${failures.length ? `${failures.length} check(s) FAILED` : "every check passed"} against ${BASE}`);
if (failures.length) {
  for (const failure of failures) console.log(`  - ${failure}`);
  process.exit(1);
}
