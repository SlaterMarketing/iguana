import { chromium } from "playwright";
const P = process.argv[2];
const BASE = "https://iguanacomedy.com";
const b = await chromium.launch();

// A real round, so the queue and the per-line void control actually render.
const cust = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "es-MX" });
const c = await cust.newPage();
await c.goto(`${BASE}/es/menu/show/?table=12`, { waitUntil: "domcontentloaded" });
await c.waitForTimeout(2500);
for (const drink of ["Victoria", "Topo Chico Margarita", "Mezcal Montelobos"]) {
  const btn = c.locator(`button[aria-label="+1 ${drink}"]`);
  if (await btn.count()) { await btn.click(); await c.waitForTimeout(200); }
}
await c.locator('input[inputmode="numeric"]').first().fill("12");
await c.locator('button:has-text("Enviar")').click();
await c.waitForTimeout(2500);
await cust.close();

const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "es-MX" });
const p = await ctx.newPage();
await p.goto(`${BASE}/mesas/entrar/`, { waitUntil: "domcontentloaded" });
await p.fill('input[name="username"]', "bar");
await p.fill('input[name="password"]', P);
await p.click('button[type="submit"]');
await p.waitForTimeout(2000);

for (const w of [320, 360, 390, 430]) {
  await p.setViewportSize({ width: w, height: 900 });
  for (const [url, label] of [[`${BASE}/mesas/`, "board+queue"], [`${BASE}/mesas/?open=12`, "breakdown"]]) {
    await p.goto(url, { waitUntil: "domcontentloaded" });
    await p.waitForTimeout(1200);
    // Open every void panel, because that is the state the buttons are visible in.
    const summaries = p.locator("details.void summary");
    const n = await summaries.count();
    for (let i = 0; i < n; i++) { await summaries.nth(i).click().catch(() => {}); }
    await p.waitForTimeout(500);
    const r = await p.evaluate((vw) => {
      const name = (el) => el.tagName.toLowerCase() + (typeof el.className === "string" && el.className.trim() ? "." + el.className.trim().split(/\s+/)[0] : "");
      const bad = [];
      for (const el of document.querySelectorAll("body *")) {
        const box = el.getBoundingClientRect();
        if (box.width === 0 && box.height === 0) continue;
        if (Math.round(box.right - vw) > 1 || Math.round(box.left) < -1) bad.push(`offscreen ${name(el)} ${Math.round(box.left)}..${Math.round(box.right)}`);
        const st = getComputedStyle(el);
        if (el.scrollWidth - el.clientWidth > 2 && !["auto", "scroll"].includes(st.overflowX)) bad.push(`clipped ${name(el)} needs ${el.scrollWidth} has ${el.clientWidth}`);
      }
      const small = [];
      for (const el of document.querySelectorAll("button, a, summary, input")) {
        const box = el.getBoundingClientRect();
        const lab = (el.tagName === "INPUT" && ["checkbox", "radio"].includes(el.type)) ? el.closest("label") : null;
        const t = lab ? lab.getBoundingClientRect() : box;
        if ((box.width || box.height) && t.height < 40) small.push(`small ${name(el)} ${Math.round(t.width)}x${Math.round(t.height)} "${(el.textContent || "").trim().slice(0, 18)}"`);
      }
      return { page: Math.max(0, document.documentElement.scrollWidth - vw), issues: [...new Set([...bad, ...small])].slice(0, 8), panels: document.querySelectorAll("details.void").length };
    }, w);
    const ok = r.page <= 1 && !r.issues.length;
    console.log(`${ok ? "ok  " : "FAIL"} ${String(w).padEnd(4)} ${label.padEnd(12)} overflow ${r.page}px, ${r.panels} void panel(s)`);
    for (const i of r.issues) console.log(`       ${i}`);
  }
}
await b.close();
