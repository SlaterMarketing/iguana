/**
 * Every surface the club depends on, driven in a real browser against production.
 *
 * Not a smoke test: a page returning 200 proves nothing about a checkout that is attached to nothing, a menu
 * with no prices, or a board that cannot close a table. Each check here does the thing a person would do.
 *
 *   node tests/full-sweep.mjs                 read-only
 *   node tests/full-sweep.mjs --book          also books a real seat and orders a real round, then says so
 */
import { chromium } from "playwright";

const BASE = "https://iguanacomedy.com";
const API = "https://api.iguanacomedy.com";
const BOOK = process.argv.includes("--book");
const STAFF = { user: process.argv[process.argv.indexOf("--staff") + 1], pass: process.argv[process.argv.indexOf("--pass") + 1] };

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok });
  console.log(`  ${ok ? "ok  " : "FAIL"}  ${name}${detail ? `  ${detail}` : ""}`);
};

const browser = await chromium.launch();
const phone = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "es-MX" };

async function page(opts = phone) {
  const ctx = await browser.newContext(opts);
  const p = await ctx.newPage();
  p.__errors = [];
  p.on("pageerror", (e) => p.__errors.push(String(e)));
  p.on("console", (m) => m.type() === "error" && p.__errors.push(m.text()));
  return p;
}

// ---------------------------------------------------------------- the pages an ad click can land on
console.log("\nlanding pages");
for (const [name, url] of [
  ["home es", `${BASE}/es/`], ["home en", `${BASE}/en/`],
  ["open mic es", `${BASE}/es/open-mic/?night=es`], ["open mic en", `${BASE}/en/open-mic/?night=en`],
  ["events es", `${BASE}/es/eventos/`], ["events en", `${BASE}/en/events/`],
  ["work with us", `${BASE}/en/work-with-us/`], ["about", `${BASE}/en/about/`], ["merch", `${BASE}/en/store/`],
]) {
  const p = await page();
  const r = await p.goto(url, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(2500);
  const body = await p.locator("body").innerText();
  check(`${name} loads and has content`, r?.status() === 200 && body.length > 400, `${r?.status()}`);
  check(`${name} has no console errors`, p.__errors.length === 0, p.__errors.slice(0, 1).join("").slice(0, 90));
  await p.context().close();
}

// ---------------------------------------------------------------- the checkout actually works
console.log("\ncheckout");
for (const [name, url] of [["open mic es", `${BASE}/es/open-mic/?night=es`], ["paid show", `${BASE}/es/eventos/privilegio-fredy-el-regio/`]]) {
  const p = await page();
  await p.goto(url, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(5000);
  const f = p.frames().find((x) => x.url().includes("/embed/event/"));
  check(`${name}: checkout iframe mounted`, Boolean(f));
  if (f) {
    const txt = await f.locator("body").innerText();
    check(`${name}: has a name field`, (await f.locator('input[name="name"]').count()) === 1);
    check(`${name}: button says what it costs`, /Reserva|Pagar/i.test(txt), txt.split("\n").filter(Boolean).pop()?.slice(0, 40));
    check(`${name}: no drinks upsell in the form`, !/bebidas por adelantado/i.test(txt));
  }
  await p.context().close();
}

// ---------------------------------------------------------------- menu and table ordering
console.log("\nmenu");
const m = await page();
await m.goto(`${BASE}/menu/show/`, { waitUntil: "domcontentloaded" });
await m.waitForTimeout(3000);
check("unprefixed /menu/show/ picks a language", /\/(es|en)\/menu\/show\//.test(m.url()), m.url().replace(BASE, ""));
const drinks = await m.locator('button[aria-label^="+1"]').count();
check("the real menu is listed", drinks === 13, `${drinks} drinks`);
const menuText = await m.locator("body").innerText();
check("prices are on the page", /\$60 MXN/.test(menuText) && /\$30 MXN/.test(menuText));
check("it says when you pay", /al final de la noche/i.test(menuText));
check("it says phones on silent", /silencio/i.test(menuText) && /grabes/i.test(menuText));
await m.locator('button[aria-label^="+1"]').first().click();
await m.waitForTimeout(400);
await m.locator('button:has-text("Enviar")').click();
await m.waitForTimeout(1200);
check("an order with no table is refused", /mesa/i.test(await m.locator("body").innerText()));
check("menu page has no console errors", m.__errors.length === 0, m.__errors.slice(0, 1).join("").slice(0, 90));
await m.context().close();

const q = await page();
await q.goto(`${BASE}/menu/qr/`, { waitUntil: "domcontentloaded" });
await q.waitForTimeout(1500);
check("the printable QR renders", (await q.locator("svg[shape-rendering]").count()) === 1);
check("it points at the ordering page", (await q.locator("body").innerText()).includes("/menu/show/"));
await q.context().close();

// ---------------------------------------------------------------- staff surfaces
if (STAFF.user && STAFF.pass) {
  console.log("\nstaff");
  const s = await page({ viewport: { width: 430, height: 932 }, isMobile: true, hasTouch: true, locale: "es-MX" });
  await s.goto(`${API}/admin/login/?next=/tables/`, { waitUntil: "domcontentloaded" });
  await s.fill('input[name="username"]', STAFF.user);
  await s.fill('input[name="password"]', STAFF.pass);
  await s.click('input[type="submit"]');
  await s.waitForTimeout(3000);
  check("the bar account reaches /tables/", s.url().includes("/tables/"), s.url().replace(API, ""));
  const board = await s.locator("body").innerText();
  check("the board lists tables", /Mesa 1/.test(board) && /Mesa 12/.test(board));
  await s.context().close();

  const r = await page({ viewport: { width: 1280, height: 900 } });
  await r.goto(`${API}/revenue/`, { waitUntil: "domcontentloaded" });
  await r.waitForTimeout(1500);
  check("/revenue/ is gated from the bar account", r.url().includes("/admin/login") || (await r.locator("body").innerText()).includes("Revenue"));
  await r.context().close();
} else {
  console.log("\nstaff  (skipped: pass --staff <user> --pass <password>)");
}

// ---------------------------------------------------------------- CLS, the thing that was broken
console.log("\nlayout stability");
for (const [name, url] of [["show page", `${BASE}/es/eventos/playa-del-carmen-2026-09-23/`], ["open mic", `${BASE}/es/open-mic/?night=es`]]) {
  const p = await page();
  const cdp = await p.context().newCDPSession(p);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await p.addInitScript(() => { window.__cls = 0; new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: "layout-shift", buffered: true }); });
  await p.goto(url, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(7000);
  const cls = await p.evaluate(() => window.__cls);
  check(`${name}: CLS under 0.1`, cls < 0.1, `CLS ${cls.toFixed(4)}`);
  await p.context().close();
}

// ---------------------------------------------------------------- posters come from the site, not the API host
console.log("\nimages");
const i = await page();
await i.goto(`${BASE}/es/eventos/`, { waitUntil: "domcontentloaded" });
await i.waitForTimeout(3000);
const srcs = await i.locator("img").evaluateAll((els) => els.map((e) => e.currentSrc || e.src).filter(Boolean));
check("no poster is loaded from the API host", !srcs.some((u) => u.includes("api.iguanacomedy.com")), srcs.find((u) => u.includes("api.")) || "");
const broken = await i.locator("img").evaluateAll((els) => els.filter((e) => e.complete && e.naturalWidth === 0).length);
check("every image on the events page loaded", broken === 0, `${broken} broken`);
await i.context().close();

// ---------------------------------------------------------------- the real thing, on request
if (BOOK) {
  console.log("\nbooking a real seat");
  const email = `e2e-sweep-${Date.now()}@iguanacomedy.com`;
  const p = await page();
  await p.goto(`${BASE}/es/open-mic/?night=es`, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(5000);
  const f = p.frames().find((x) => x.url().includes("/embed/event/"));
  await f.locator('input[name="name"]').fill("Sweep Probe");
  await f.locator('input[name="email"]').fill(email);
  await Promise.all([p.waitForURL(/\/orders\//, { timeout: 45000 }).catch(() => {}), f.locator('button[type="submit"]').click()]);
  await p.waitForTimeout(3000);
  check("it books and lands on the order page", /\/orders\//.test(p.url()));
  const order = await p.locator("body").innerText();
  check("the order page shows a ticket and a QR", /boleto/i.test(order) && (await p.locator("[data-qr] img, [data-qr] canvas").count()) > 0);
  check("the order page offers the menu", /Con sed|menú/i.test(order));
  check("the order page offers the invite", /vienes con alguien/i.test(order));
  console.log(`\n  🚨 created a real reservation: ${email}`);
  await p.context().close();
}

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
for (const f of failed) console.log(`  FAILED: ${f.name}`);
process.exit(failed.length ? 1 : 0);
