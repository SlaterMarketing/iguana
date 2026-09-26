import { chromium } from "playwright";
const P = process.argv[2], TOKEN = process.argv[3];
const BASE = "https://iguanacomedy.com";
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "es-MX" })).newPage();
await p.goto(`${BASE}/mesas/entrar/`, { waitUntil: "domcontentloaded" });
await p.fill('input[name="username"]', "door");
await p.fill('input[name="password"]', P);
await p.click('button[type="submit"]');
await p.waitForTimeout(2000);
console.log("login ->", p.url().replace(BASE, ""));

await p.goto(`${BASE}/mesas/puerta/`, { waitUntil: "domcontentloaded" });
await p.waitForTimeout(1500);
const read = async () => (await p.locator("#verdict").innerText()).replace(/\n/g, " | ");

// Type the code, the fallback path that works on every phone.
const type = async (code) => {
  await p.fill("#code", code);
  await p.click('#manual button[type="submit"]');
  await p.waitForTimeout(1500);
  return read();
};
console.log("1st scan  :", await type(TOKEN));
console.log("2nd scan  :", await type(TOKEN));
console.log("bad code  :", await type("not-a-real-code"));
// The QR holds a URL, so make sure that form works too.
console.log("as a URL  :", await type(`${BASE}/checkin/${TOKEN}/`));
const undo = p.locator('#verdict button');
if (await undo.count()) { await undo.first().click(); await p.waitForTimeout(1500); console.log("after undo:", await read()); }
console.log("after undo, scan again:", await type(TOKEN));
console.log("page overflow at 390:", await p.evaluate(() => Math.max(0, document.documentElement.scrollWidth - 390)));
await b.close();
