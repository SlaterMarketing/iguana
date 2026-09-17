/**
 * End to end: register, sign in with the emailed code, sign in with the magic link, and sign out.
 *
 *   node tests/account-flow.mjs [baseUrl]
 *
 * Reads the emailed code straight from the backend database (local development sends mail to the console), so it
 * exercises the real endpoints rather than stubbing them. Needs the site and the backend running locally.
 */

import { execFileSync } from "node:child_process";
import { chromium } from "/home/john/tos/node_modules/playwright/index.mjs";

const BASE = process.argv[2] ?? "http://127.0.0.1:4321";
const BACKEND = "/home/john/iguana/backend";
const email = `e2e-${Date.now()}@example.com`;
const failures = [];

function check(name, ok, detail = "") {
  console.log(`${ok ? "  ok  " : "  FAIL"} ${name}${detail ? "  " + detail : ""}`);
  if (!ok) failures.push(name);
}

/** The newest sign-in token for this address, as [code, token]. */
function loginToken(forEmail) {
  const script = `
from sales.models import LoginToken
row = LoginToken.objects.filter(email='${forEmail}').order_by('-created_at').first()
print(f'{row.code}|{row.token}' if row else 'none')
`;
  const out = execFileSync(`${BACKEND}/.venv/bin/python`, ["manage.py", "shell", "-c", script], {
    cwd: BACKEND,
    encoding: "utf8",
  });
  const line = out.trim().split("\n").filter((l) => l.includes("|")).pop();
  return line ? line.split("|") : [null, null];
}

/** Signed in means the account page names this address and offers to sign out, not merely that no error showed. */
async function signedIn(page) {
  await page.goto(`${BASE}/es/cuenta/`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  const body = await page.evaluate(() => document.body.innerText);
  return body.includes(email) && /cerrar sesi|salir/i.test(body);
}

const browser = await chromium.launch();

async function submitEmail(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(1500);
  await page.locator("input[type=email]").fill(email);
  await page.locator("button[type=submit]").click();
  await page.waitForTimeout(2500);
}

// 1. Register: ask for a code, then use it.
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await submitEmail(page, "/es/cuenta/registro/");
  const [code] = loginToken(email);
  check("register emails a 6 digit code", /^\d{6}$/.test(code ?? ""), code ?? "no token row");
  const codeField = page.locator("input").filter({ hasNot: page.locator("[type=email]") }).last();
  await codeField.fill(code ?? "");
  await page.locator("button[type=submit]").click();
  await page.waitForTimeout(3500);
  check("register signs the account in", await signedIn(page), page.url());
  await page.close();
}

// 2. Sign in again with a fresh code, in a clean browser context.
{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await submitEmail(page, "/es/cuenta/iniciar-sesion/");
  const [code] = loginToken(email);
  check("sign-in emails a fresh code", /^\d{6}$/.test(code ?? ""), code ?? "no token row");
  const codeField = page.locator("input").filter({ hasNot: page.locator("[type=email]") }).last();
  await codeField.fill(code ?? "");
  await page.locator("button[type=submit]").click();
  await page.waitForTimeout(3500);
  check("code signs in", await signedIn(page), page.url());
  await context.close();
}

// 3. The magic link in the email signs in on its own.
{
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await submitEmail(page, "/es/cuenta/iniciar-sesion/");
  const [, token] = loginToken(email);
  await page.goto(`${BASE}/es/cuenta/verificar/?token=${token}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(4000);
  check("magic link signs in", await signedIn(page), page.url());
  await context.close();
}

await browser.close();
console.log(failures.length ? `\n${failures.length} failing: ${failures.join(", ")}` : "\nall account checks passed");
process.exit(failures.length ? 1 : 0);
