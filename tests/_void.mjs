import { chromium } from "playwright";
const P = process.argv[2];
const BASE = "https://iguanacomedy.com";
const b = await chromium.launch();
const staff = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "es-MX" });
const s = await staff.newPage();
await s.goto(`${BASE}/mesas/entrar/`, { waitUntil: "domcontentloaded" });
await s.fill('input[name="username"]', "bar");
await s.fill('input[name="password"]', P);
await s.click('button[type="submit"]');
await s.waitForTimeout(2000);

// Give Victoria a known count.
await s.goto(`${BASE}/mesas/inventario/`, { waitUntil: "domcontentloaded" });
await s.waitForTimeout(1200);
const vcard = () => s.locator('.it:has-text("Victoria")').first();
await vcard().locator('input[name="set"]').fill("20");
await vcard().locator('button:has-text("Poner")').click();
await s.waitForTimeout(1500);
const qty = async () => {
  await s.goto(`${BASE}/mesas/inventario/`, { waitUntil: "domcontentloaded" });
  await s.waitForTimeout(1000);
  const t = await vcard().innerText();
  return (t.match(/(\d+(?:\.\d+)?)\s*botella/) || [])[1];
};
console.log(`start: ${await qty()} botellas`);

// Customer orders 2 Victorias at table 12.
const cust = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "es-MX" });
const c = await cust.newPage();
await c.goto(`${BASE}/es/menu/show/?table=12`, { waitUntil: "domcontentloaded" });
await c.waitForTimeout(2500);
await c.locator('button[aria-label="+1 Victoria"]').click();
await c.waitForTimeout(250);
await c.locator('button[aria-label="+1 Victoria"]').click();
await c.waitForTimeout(250);
await c.locator('input[inputmode="numeric"]').first().fill("12");
await c.waitForTimeout(250);
await c.locator('button:has-text("Enviar")').click();
await c.waitForTimeout(2500);
await cust.close();

// Deliver it, so stock has left.
await s.goto(`${BASE}/mesas/`, { waitUntil: "domcontentloaded" });
await s.waitForTimeout(1500);
const d = s.locator('form[action="/tables/12/close/"] button').first();
if (await d.count()) { await d.click(); await s.waitForTimeout(2000); }
console.log(`after delivery: ${await qty()} botellas  (expect 18)`);

// Open the breakdown and take the line off as "not made".
await s.goto(`${BASE}/mesas/?open=12`, { waitUntil: "domcontentloaded" });
await s.waitForTimeout(1500);
const due = async () => {
  const t = await s.locator("#t12").innerText();
  return t.split("\n").filter((l) => /\$|MXN/.test(l)).join(" | ");
};
console.log(`due before void: ${await due()}`);
await s.locator('#t12 details.void summary').first().click();
await s.waitForTimeout(400);
await s.locator('#t12 button[value="NOT_MADE"]').first().click();
await s.waitForTimeout(2500);
console.log(`after void (not made): ${await qty()} botellas  (expect 20 back)`);
await s.goto(`${BASE}/mesas/?open=12`, { waitUntil: "domcontentloaded" });
await s.waitForTimeout(1500);
const card = await s.locator("#t12").innerText();
console.log(`due after void: ${await due()}`);
console.log(`struck through and says why: ${/No se preparó/i.test(card)}`);
await b.close();
