/**
 * End to end: reserve a seat at an open mic, through the real checkout iframe.
 *
 *   node tests/reserve-flow.mjs [baseUrl]
 *
 * Open mics are pay-at-door while Stripe is not connected, so this completes a real booking against the local
 * backend and then checks the order page and the database row it wrote.
 */

import { execFileSync } from "node:child_process";
import { chromium } from "/home/john/tos/node_modules/playwright/index.mjs";

const BASE = process.argv[2] ?? "http://127.0.0.1:4321";
const BACKEND = "/home/john/iguana/backend";
const email = `e2e-seat-${Date.now()}@example.com`;
const failures = [];

function check(name, ok, detail = "") {
  console.log(`${ok ? "  ok  " : "  FAIL"} ${name}${detail ? "  " + detail : ""}`);
  if (!ok) failures.push(name);
}

function django(script) {
  return execFileSync(`${BACKEND}/.venv/bin/python`, ["manage.py", "shell", "-c", script], {
    cwd: BACKEND,
    encoding: "utf8",
  })
    .trim()
    .split("\n")
    .pop();
}

const slug = django(`
from catalog.models import Event
row = Event.objects.filter(tags__contains=[] if False else []).none()
import datetime
from django.utils import timezone
row = Event.objects.filter(date__gte=timezone.now(), status='ACTIVE').order_by('date')
print(next((e.slug for e in row if 'open-mic' in (e.tags or [])), 'none'))
`);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });

await page.goto(`${BASE}/es/eventos/${slug}/`, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3000);
check("the open mic page loads", (await page.title()).length > 0, slug);

// The checkout lives in an iframe injected by the tracker script.
await page.locator('a[href="#checkout"], a[href*="#tickets"]').first().click().catch(() => {});
await page.waitForTimeout(3500);
const frame = page.frames().find((f) => f.url().includes("/embed/event/"));
check("the checkout iframe mounts", Boolean(frame), frame ? frame.url().slice(-40) : "no iframe");

if (frame) {
  // Nothing but the quantity stepper shows until a seat is chosen, which is the point of the simplified checkout.
  check("checkout opens with the details hidden", !(await frame.locator("input[type=email]").first().isVisible()));
  await frame.locator("button", { hasText: "+" }).first().click();
  await frame.waitForTimeout(800);
  check("choosing a seat reveals the form", await frame.locator("input[type=email]").first().isVisible());
  await frame.locator("input[name=name]").first().fill("E2E Tester");
  await frame.locator("input[type=email]").first().fill(email);
  await frame.locator("button[type=submit]").first().click();
  await page.waitForTimeout(7000);

  const order = django(`
from sales.models import Order
row = Order.objects.filter(customer_email='${email}').order_by('-created_at').first()
print(f'{row.status}|{row.locale}|{row.event_name}|{row.pay_at_door_cents}' if row else 'none')
`);
  check("the reservation is recorded", order !== "none", order);
  check("it is stored in the language it was booked in", order.split("|")[1] === "es", order.split("|")[1]);
  check("the event name is the Spanish one", /Espa|Ingl/.test(order.split("|")[2] ?? ""), order.split("|")[2]);
  const body = await page.evaluate(() => document.body.innerText);
  check("the person lands on a confirmation", /reserva|orden|boleto|confirm/i.test(body), page.url());
}

await browser.close();
console.log(failures.length ? `\n${failures.length} failing: ${failures.join(", ")}` : "\nall reservation checks passed");
process.exit(failures.length ? 1 : 0);
