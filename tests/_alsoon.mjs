import { chromium } from "playwright";
const b = await chromium.launch();
for (const [label, url] of [["es", "https://iguanacomedy.com/es/eventos/privilegio-fredy-el-regio/"],
                            ["en", "https://iguanacomedy.com/en/events/privilegio-fredy-el-regio/"]]) {
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: label === "es" ? "es-MX" : "en-GB" });
  const p = await ctx.newPage();
  await p.goto(url, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(3500);
  const links = p.locator('a[href*="/eventos/"], a[href*="/events/"]');
  const panel = await p.locator('text=/Todavía hay lugar|Still on sale/').count();
  console.log(`\n${label}: heading present ${panel > 0}`);
  const rows = await p.evaluate(() => {
    const head = [...document.querySelectorAll("p")].find((e) => /Todavía hay lugar|Still on sale/i.test(e.textContent || ""));
    if (!head) return [];
    return [...head.parentElement.querySelectorAll("a")].map((a) => ({
      href: a.getAttribute("href"),
      text: a.innerText.replace(/\n/g, " · ").trim(),
      h: Math.round(a.getBoundingClientRect().height),
    }));
  });
  for (const r of rows) console.log(`   ${r.h}px  ${r.text}  ->  ${r.href}`);
  // every offered link must actually load and not itself be sold out
  for (const r of rows) {
    const res = await p.goto(`https://iguanacomedy.com${r.href}`, { waitUntil: "domcontentloaded" });
    await p.waitForTimeout(2000);
    const body = await p.locator("body").innerText();
    console.log(`   ${r.href} -> ${res.status()} soldout=${/AGOTADO|SOLD OUT/i.test(body)}`);
  }
  await ctx.close();
}
await b.close();
