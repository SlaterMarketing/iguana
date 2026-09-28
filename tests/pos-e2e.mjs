/**
 * End to end against the point of sale, the way a waiter and a manager use it on a night.
 *
 *   FLOOR_PASS=... API_KEY=... node tests/pos-e2e.mjs [--base https://iguanacomedy.com]
 *
 * 🚨 It needs the fixtures from a setup run (staff "E2E Gerente" 4242 / "E2E Mesero" 4343, table 99 "E2E",
 * category "E2E prueba" with "E2E Cerveza" (recipe: 1 "E2E stock", modifier "E2E Michelada") and "E2E Shot"),
 * and it refuses to start while a real till shift is open, because it opens and closes one. Everything it makes
 * is deleted by the cleanup run. Nothing here touches real stock, real products or real money.
 */
import { chromium } from "playwright";

const args = process.argv.slice(2);
const BASE = (args[args.indexOf("--base") + 1] && args.includes("--base") ? args[args.indexOf("--base") + 1] : "https://iguanacomedy.com").replace(/\/$/, "");
const OUT = "/tmp/claude-1000/-home-john-iguana/4efc6e7b-85c5-4bf4-9ee7-3edeeda0bddb/scratchpad/e2e";
const FLOOR = { user: process.env.FLOOR_USER || "mesero", pass: process.env.FLOOR_PASS };
const results = [];
let failures = 0;
function check(name, ok, detail = "") {
  results.push(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  (" + detail + ")" : ""}`);
  if (!ok) failures++;
}
const money = (s) => Math.round(parseFloat(String(s).replace(/[^0-9.]/g, "")) * 100);

const b = await chromium.launch();
let current = null;
process.on('unhandledRejection', async (e) => { console.log(results.join('\n')); console.log('STOPPED:', e.message.split('\n')[0]); try { await current.screenshot({ path: `${OUT}-stopped.png` }); } catch (x) {} process.exit(1); });

async function signIn(ctx, pin) {
  const p = await ctx.newPage();
  p.on("pageerror", (e) => check("no script error on " + p.url(), false, e.message));
  await p.goto(BASE + "/mesas/entrar/?next=/pos/");
  if (p.url().includes("/mesas/entrar/")) {
    await p.fill('input[name="username"]', FLOOR.user);
    await p.fill('input[name="password"]', FLOOR.pass);
    await p.click('button[type="submit"]');
  }
  await p.waitForURL(/\/pos\/entrar\//);
  for (const k of pin) await p.click(`[data-k="${k}"]`);
  await p.click("button.ok");
  await p.waitForURL(BASE + "/pos/");
  current = p;
  return p;
}
async function total(p) { return money(await p.textContent("#t-total")); }
async function settle(p) { await p.waitForTimeout(900); }
async function toastText(p) { const t = p.locator(".msg").last(); await t.waitFor({ timeout: 6000 }); return t.textContent(); }

// ------------------------------------------------------------ A: the waiter, on a tablet
const tablet = await b.newContext({ viewport: { width: 1180, height: 820 } });
const popups = [];
tablet.on("page", (pg) => { if (pg.url().includes("/pos/imprimir/") || pg.url() === "about:blank") popups.push(pg); });
let p = await signIn(tablet, "4343");
check("waiter signs in with PIN and lands on the map", (await p.textContent(".top")).includes("E2E Mesero"));
await p.screenshot({ path: `${OUT}-map.png` });

await p.click('.tbl:has-text("E2E")');
await p.waitForURL(/\/pos\/cuenta\//);
const cuentaUrl = p.url();
await p.click('#cats button:has-text("E2E prueba")');
await p.click('#items button:has-text("E2E Shot")'); await p.click('#items button:has-text("E2E Shot")');
await p.click('#items button:has-text("E2E Cerveza")');
await p.waitForSelector("#d-mods[open]");
await p.click('#mods-body button:has-text("E2E Michelada")');
await p.fill("#mods-note", "sin sal");
await p.click("#mods-ok");
await settle(p);
check("three lines, one with the michelada priced in", (await p.locator("#lines tr").count()) === 3 && (await total(p)) === 25000, `total ${await total(p)}`);

await p.click('#lines tr:has-text("E2E Shot") >> nth=0');
await p.click('[data-t="plus"]');
await settle(p);
check("+ on an unsent line", (await total(p)) === 34000, `total ${await total(p)}`);

await p.click('[data-f="send"]');
await settle(p);
check("Enviar sends everything", (await p.textContent("#h-status")).includes("Todo enviado"));
await p.waitForTimeout(1200);
check("no printer yet: the comanda opens for the tablet to print", popups.length >= 1, `${popups.length} popup(s)`);
for (const pg of popups.splice(0)) await pg.close().catch(() => {});

await p.click('#lines tr:has-text("E2E Cerveza")');
await p.click('[data-t="void"]');
await p.waitForSelector("#d-void[open]");
await p.click('#void-reasons [data-r="NOT_MADE"]');
await p.click("#void-ok");
const refusal = await toastText(p);
check("voiding a sent drink without a manager is refused", /gerente/i.test(refusal), refusal);
await p.fill("#void-pin", "4242"); await p.fill("#void-note", "prueba");
await p.click("#void-ok");
await settle(p);
check("with the manager's PIN it is voided and off the bill", (await total(p)) === 27000, `total ${await total(p)}`);

await p.click('[data-f="discount"]');
await p.click('#disc-pcts [data-p="10"]');
await p.fill("#disc-reason", "prueba"); await p.fill("#disc-pin", "4242");
await p.click("#disc-ok");
await settle(p);
check("10% discount with manager PIN", (await total(p)) === 24300, `total ${await total(p)}`);

await p.click('[data-f="split"]');
await p.waitForSelector("#d-split[open]");
const shotBoxes = p.locator('#split-list label:has-text("E2E Shot") input');
await shotBoxes.last().check();
await p.click("#split-ok");
const splitMsg = await toastText(p);
check("Dividir moves a line to its own check", /separó/.test(splitMsg), splitMsg);

await p.click('[data-f="pay"]');
const noShift = await toastText(p);
check("no till shift: charging is refused with a reason", /caja/i.test(noShift), noShift);
await p.screenshot({ path: `${OUT}-cuenta-waiter.png` });
await p.close();

// ------------------------------------------------------------ B: the manager
p = await signIn(tablet, "4242");
await p.goto(BASE + "/pos/caja/");
await p.fill('input[name="opening"]', "500");
await p.click('button:has-text("Abrir caja")');
check("manager opens the till", (await p.textContent("body")).includes("Turno abierto por E2E Gerente"));

await p.goto(cuentaUrl);
await p.waitForSelector("#lines tr");
const due = await total(p);
await p.click('[data-f="pay"]');
await p.waitForSelector("#d-pay[open]");
await p.click('#methods [data-m="CARD"]');
await p.click('#split-even button >> nth=0');
await p.fill("#pay-ref", "4242");
await p.click("#pay-ok");
await p.waitForTimeout(1500);
check("half by terminal card", (await p.textContent("#t-due")).length > 0 && money(await p.textContent("#t-paid")) > 0, `paid ${await p.textContent("#t-paid")}`);
await p.click('#methods [data-m="CASH"]');
await p.fill("#pay-received", "500");
await p.dispatchEvent("#pay-received", "input");
const change = money(await p.textContent("#pay-change"));
await p.click("#pay-ok");
await p.waitForURL(BASE + "/pos/", { timeout: 8000 }).catch(() => {});
check("the rest in cash with change, check closes and returns to the map", p.url() === BASE + "/pos/", `change shown ${change}, due was ${due}`);
for (const pg of popups.splice(0)) await pg.close().catch(() => {});

// the split check, still on table 99
await p.click('.tbl:has-text("E2E")');
await p.waitForURL(/\/pos\/cuenta\//);
check("the split check is still open on the table", (await total(p)) > 0, `total ${await total(p)}`);
await p.click('[data-f="pay"]');
await p.click('#methods [data-m="TRANSFER"]');
await p.fill("#pay-ref", "SPEI prueba");
await p.click("#pay-ok");
await p.waitForURL(BASE + "/pos/", { timeout: 8000 }).catch(() => {});
check("split check paid by transfer", p.url() === BASE + "/pos/");

// a customer QR order
const qr = await fetch(BASE + "/api/public/v1/menu?locale=es", { headers: { Authorization: "Bearer " + process.env.API_KEY } }).then((r) => r.json());
const shot = qr.categories.flatMap((c) => c.items).find((i) => i.name === "E2E Shot");
const placed = await fetch(BASE + "/api/public/v1/table-orders", {
  method: "POST", headers: { Authorization: "Bearer " + process.env.API_KEY, "Content-Type": "application/json" },
  body: JSON.stringify({ table: 99, items: { [shot.id]: 1 }, name: "E2E", note: "prueba", lang: "es" }),
});
check("customer QR order accepted", placed.status === 200, String(placed.status));
await p.waitForTimeout(6000);
check("the map flashes the table orange", await p.locator('.tbl.order:has-text("E2E")').count() === 1);
await p.click('.tbl:has-text("E2E")');
await p.waitForURL(/\/pos\/cuenta\//);
check("the QR line waits, marked QR", await p.locator('#lines tr.qr').count() === 1);
await p.click('[data-f="send"]');
await settle(p);
await p.click('[data-f="more"]').catch(() => {});
await p.click('[data-f="cancel"]');
await p.fill("#cancel-reason", "prueba e2e");
await p.click("#cancel-ok");
await p.waitForURL(BASE + "/pos/", { timeout: 8000 }).catch(() => {});
check("manager cancels a check without typing a PIN again", p.url() === BASE + "/pos/");

await p.goto(BASE + "/pos/barra/");
const pending = await p.locator('.ko:has-text("E2E")').count();
check("the bar screen lists the E2E comandas", pending >= 1, `${pending}`);
while (await p.locator('.ko:has-text("E2E") button').count()) { await p.locator('.ko:has-text("E2E") button').first().click(); await p.waitForLoadState("load"); }
check("the bar marks them done", (await p.locator('.ko:has-text("E2E")').count()) === 0);

await p.goto(BASE + "/pos/caja/");
const expected = money((await p.textContent("body")).match(/Efectivo esperado \$[0-9,.]+/)[0]);
await p.fill('input[name="counted_cash"]', String(expected / 100));
await p.click('button:has-text("Hacer corte")');
await p.waitForURL(/\/pos\/caja\/.+\?print=1/);
const corte = await p.textContent("body");
check("corte with the counted cash matching", corte.includes("Diferencia") && /Diferencia\s*\$0\.00/.test(corte.replace(/\s+/g, " ")), `expected ${expected}`);
await p.screenshot({ path: `${OUT}-corte.png`, fullPage: true });

await p.goto(BASE + "/pos/reportes/");
check("reports list what was sold", (await p.textContent("body")).includes("E2E Shot"));
await p.close();
await tablet.close();

// ------------------------------------------------------------ C: a phone, dialogs open, no sideways scroll
for (const w of [320, 390]) {
  const phone = await b.newContext({ viewport: { width: w, height: 760 }, isMobile: true, hasTouch: true });
  phone.on("page", (pg) => { if (pg.url().includes("/pos/imprimir/")) pg.close().catch(() => {}); });
  const q = await signIn(phone, "4343");
  await q.click('.tbl:has-text("E2E")');
  await q.waitForURL(/\/pos\/cuenta\//);
  await q.click('#cats button:has-text("E2E prueba")');
  await q.click('#items button:has-text("E2E Shot")');
  await q.waitForTimeout(800);
  const over = async () => q.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  const shots = [];
  for (const [label, open] of [["cuenta", null], ["mas", async () => q.click(".fkeys .more")], ["dividir", async () => { await q.click('[data-f="split"]'); }],
                               ["descuento", async () => { await q.keyboard.press("Escape"); await q.click(".fkeys .more"); await q.click('[data-f="discount"]'); }]]) {
    if (open) await open();
    await q.waitForTimeout(400);
    const o = await over();
    check(`phone ${w}: ${label} fits`, o === 0, `overflow ${o}`);
    shots.push(label);
    await q.screenshot({ path: `${OUT}-phone${w}-${label}.png` });
  }
  await q.keyboard.press("Escape");
  const token = await q.evaluate(() => JSON.parse(document.getElementById("boot").textContent).payUrl.split("/pos/pagar/")[1]);
  const pay = await phone.newPage();
  await pay.goto(BASE + "/pos/pagar/" + token);
  check(`phone ${w}: the customer's pay page shows the bill`, (await pay.textContent("body")).includes("E2E Shot") && (await pay.evaluate(() => document.documentElement.scrollWidth - innerWidth)) === 0);
  await phone.close();
}
await b.close();
console.log(results.join("\n"));
console.log(failures ? `\n${failures} FAILED` : "\nALL PASSED");
process.exit(failures ? 1 : 0);
