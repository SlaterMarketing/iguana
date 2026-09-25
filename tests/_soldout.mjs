import { chromium } from "playwright";
const BASE = "https://iguanacomedy.com";
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 1000 }, locale: "es-MX" });
const p = await ctx.newPage();

for (const [label, url] of [["home", `${BASE}/es/`], ["events", `${BASE}/es/eventos/`], ["detail", `${BASE}/es/eventos/privilegio-fredy-el-regio/`]]) {
  await p.goto(url, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(3500);
  const body = await p.locator("body").innerText();
  const priv = body.split("\n").findIndex((l) => /PRIVILEGIO/i.test(l));
  const near = body.split("\n").slice(Math.max(0, priv - 4), priv + 12).join(" | ");
  console.log(`\n${label}`);
  console.log(`  says AGOTADO:        ${/AGOTADO/i.test(body)}`);
  console.log(`  still says reserve:  ${/mejor reserva pronto|Más de la mitad/i.test(near)}`);
  console.log(`  still shows price:   ${/Desde \$300/.test(near)}`);
  if (label !== "detail") {
    const band = await p.locator('div:has-text("AGOTADO")').last().boundingBox().catch(() => null);
    const size = await p.evaluate(() => {
      const el = [...document.querySelectorAll("p")].find((e) => /^AGOTADO$/i.test((e.textContent || "").trim()));
      return el ? Math.round(parseFloat(getComputedStyle(el).fontSize)) : null;
    });
    console.log(`  AGOTADO font size:   ${size}px`);
  } else {
    const size = await p.evaluate(() => {
      const el = [...document.querySelectorAll("p")].find((e) => /^AGOTADO$/i.test((e.textContent || "").trim()));
      return el ? Math.round(parseFloat(getComputedStyle(el).fontSize)) : null;
    });
    console.log(`  AGOTADO font size:   ${size}px`);
    console.log(`  old vague message:   ${/no están disponibles por ahora/i.test(body)}`);
    console.log(`  checkout form gone:  ${(await p.locator('input[name="email"]').count()) === 0}`);
  }
  console.log(`  context: ${near.slice(0, 150)}`);
}
await b.close();
