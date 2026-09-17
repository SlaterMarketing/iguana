# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Iguana Comedy (stand-up promoter, Quintana Roo, Mexico). Two apps in one repo: a bilingual **Astro 5 SSR site**
(repo root) and a **Django backend** (`backend/`) that replaced the Kintana SaaS the site was originally built on.
Repo is `SlaterMarketing/iguana` (public, client-owned). Backend, deploy and migration work lives on branch
`backend-django`, which has not been pushed: ask before pushing anywhere.

## Commands

```bash
# Site (Node 20, see .node-version)
npm install
npm run dev                      # Astro dev server; needs .env + .dev.vars (copy the .example files)
npm run build                    # Cloudflare Pages build (default adapter) + scripts/verify-dist.mjs
npm run build:node               # ASTRO_ADAPTER=node standalone server -> dist/server/entry.mjs (what production runs)
npm run start:node               # run that build
npx astro check                  # type check (pre-existing errors on Locals.brandOverrides in middleware.ts)

# Backend (Django 6, SQLite locally via config.py, Postgres in production)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp config_example.py config.py   # DEBUG=True, SITE_URLS, PUBLIC_API_KEYS, EMAIL_BACKEND console for local
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 127.0.0.1:8000
.venv/bin/python manage.py test api                                            # all backend tests
.venv/bin/python manage.py test api.tests.CheckoutTests.test_member_free_tickets_then_guest_discount  # one test

# Data (one-off / re-runnable, fill blanks unless --overwrite)
.venv/bin/python manage.py import_kintana_export ~/iguana-migration/export     # client's Kintana CSV export
.venv/bin/python manage.py import_archive                                      # Wayback-recovered comedians/venues/posters/merch
.venv/bin/python manage.py seed_site_defaults                                  # form endpoints + membership plan pricing
.venv/bin/python manage.py send_test_email someone@example.com                 # mail test as DEFAULT_FROM_EMAIL

# Production (run from ansible/; inventory + group_vars/all are gitignored, secrets come from ~/.credentials)
ansible-playbook deploy.yml                    # rsync this checkout, build, migrate, restart, apply mail.yml
ansible-playbook deploy.yml --tags all,certs   # also issue missing Let's Encrypt certs listed in cert_sets
ansible-playbook email_check.yml               # end-to-end mail verification (asserts on DNS, DKIM, delivery)
```

Local pairing: backend on `127.0.0.1:8000`, site on `127.0.0.1:4321` with `.env` / `.dev.vars` setting
`PUBLIC_KINTANA_BASE_URL=http://127.0.0.1:8000` and `PUBLIC_KINTANA_API_KEY` to a key from `config.PUBLIC_API_KEYS`.

## Architecture

### The site still talks "Kintana", the backend answers it

The Astro code calls `@kintana/sdk` (vendored tarball in `vendor/`) everywhere. Rather than rewrite the site, the
Django backend implements the same HTTP contract, so only the base URL and key differ:

- `backend/api/public_views.py`: `/api/public/v1/{events,artists,venues,endpoints,store,files,site}`
- `backend/api/fan_views.py`: `/api/fan/v1/*` (magic-link sign-in, profile, tickets, memberships, redeem codes,
  credit transfers, Stripe subscribe / one-off / billing portal)
- `backend/api/embed_views.py`: `/_t/k.js` (drop-in for Kintana's tracker script), `/embed/event/<id>` (checkout
  iframe), `/orders/<token>/`, staff `/checkin/<token>/`, `/api/stripe/webhook`, `/api/ingest/*`
- `backend/api/serializers.py` produces the exact SDK JSON shapes. When the site needs a field, check the SDK
  types in `node_modules/@kintana/sdk/dist/*.d.ts` and add it there.

Auth: the site's key arrives as `Authorization: Bearer` (checked by `api_view` in `api/auth.py`); signed-in fans add
`X-Customer-Authorization: Bearer <signed token>` issued by `auth/verify`. Browser calls rely on
`api/middleware.py` CORS for `SITE_URLS`.

Checkout flow: `EventCheckoutWidget.astro` renders `data-kintana-widget="event:<id>"`; `k.js` injects the iframe,
posts the fan token in, and follows `kintana-embed-checkout-success` to the order page. Prices are always
computed server-side in `sales/services.py::price_cart` (member free tickets priciest-first, then guest discount;
member pricing only when checkout email equals the signed-in member). With `DEBUG=True` and no Stripe keys the
iframe offers a simulated payment; in production without keys it refuses payment.

Backend apps: `catalog` (venues, artists, events, lineup, ticket types, store, form endpoints, site files),
`crm` (contacts, lists, campaigns, inbox history, tracked events), `sales` (orders, tickets, memberships, plans,
redeem codes, credit transfers, login tokens), `api` (views only, no models). Image fields hold either absolute
URLs or `/media/...` paths; `serializers.media()` makes them absolute with `BACKEND_URL`.

### Site structure

- `output: "server"`: every page renders per request from the API. Pages hold no data at build time.
- Routes are locale-prefixed and translated: `src/i18n/routes.ts` maps route keys to `/en/...` and `/es/...`
  slugs; always build links with `localizePath(locale, key, params)`. UI strings live in `src/i18n/ui.ts` via
  `t(locale, key, vars)`.
- `src/pages/en/**` and `src/pages/es/**` are parallel thin wrappers around shared components
  (`<EventsIndexPage locale="es" />`). A page change usually means touching both trees or the shared component.
- `src/middleware.ts`: `/` picks a locale (cookie, Accept-Language), 301s Framer-era URLs via
  `legacyRedirectTarget` in `src/lib/legacy-paths.ts`, and loads brand-image overrides from `listFiles`.
- `src/lib/kintana-env.ts` reads env from Cloudflare runtime, `process.env`, then `import.meta.env`. Public vars
  must use Astro's `PUBLIC_` prefix; `KINTANA_SECRET_API_KEY` is server-only and must never reach islands.
- React islands only where hooks are needed: contact form (`ContactFormIsland`, `useKintanaSubmit(slug)` with
  endpoint slugs `contact`, `perform-with-us`, `hotels-and-resorts`), account/sign-in, membership (Stripe
  Elements), event member offer.
- Event dates come from the API as `YYYY-MM-DD` (Cancun day) and the API sets `status: "past"` by the Cancun
  calendar, so filter on status rather than comparing against the server clock (`src/lib/home-page-data.ts`).
- Static brand media (logo, city photos, hero video) is self-hosted in `public/media/`, not on Kintana.
- `astro.config.mjs` switches adapter on `ASTRO_ADAPTER=node`; the Cloudflare build keeps its `react-dom/server.edge`
  aliases, the Node build must not use them.

### Production

One VPS (VPS.org `free` account, 38.86.78.36, user `iguana`, creds `~/.credentials/vpsorg/iguanacomedy/`).
nginx fronts supervisor programs `iguana:iguana-web` (Node, :3000) and `iguana:iguana-api` (gunicorn, :8001);
Postgres `iguana`. `iguanacomedy.com` is canonical (DNS on Cloudflare, records must stay DNS-only: proxied records
pointing at Cloudflare IPs caused the old Error 1000); `iguanacomedy.mx` 301s to it; API at
`api.iguanacomedy.com` (and `api.iguanacomedy.mx`). Admin: `https://api.iguanacomedy.com/admin/`.

- `ansible/files/nginx.conf.j2` renders TLS blocks only for certificates that exist (`cert_sets`), so redeploys
  never strip HTTPS. nginx is 1.24: use `listen 443 ssl http2`, not `http2 on`.
- Code is rsynced from the local checkout (not git-pulled). `backend/media/` syncs add-only so server uploads survive.
- Mail (`ansible/mail.yml`): Postfix + OpenDKIM for every zone in `mail_zones` (`iguanacomedy.mx` and
  `iguanacomedy.com`, each with its own DKIM key under selector `mail`), one mail host `mail.iguanacomedy.mx`
  because the PTR points there. `mail_human_aliases` (hello, info, bills, andrew, john) deliver to the local
  `inbox` user **and** forward to `mail_forwards`; role/DSN addresses deliver locally only; no catch-all, so
  anything else is rejected at RCPT. 38.86.78.0/24 is on the Spamhaus PBL, so Postfix prefers IPv6 (Gmail
  rejects the v4 address).

### Everything is bilingual, always

The owner's rule: every string a visitor or customer sees exists in English and Spanish. Three guards enforce it,
and a new string should go through one of them rather than be written inline:

- **Site:** `t(locale, key)` with keys in both `ui.en` and `ui.es` (`src/i18n/ui.ts`), or a component-local
  `{ en, es }[locale]` dictionary. `t()` silently falls back to English for a missing Spanish key, so
  `scripts/check-i18n.mjs` runs before every `build`/`build:node` and fails on a missing key or mismatched `{slot}`.
  English prop defaults on shared components must be locale-aware, not English literals.
- **Backend (checkout iframe, order page, confirmation and sign-in emails, check-in, API errors):** English source
  strings go through `tr(lang, text, *params)` / `{% t lang "..." %}` / `CheckoutError('...', *params)` with Spanish
  in `backend/sales/i18n.py` (positional `{0}` slots). `api.tests.TranslationTests` scans the code for every such
  string and fails when one has no Spanish or a slot differs; it also asserts it found over 100 strings, so a broken
  scan cannot pass by matching nothing.
- **How the language travels:** the site's checkout widget sets `data-kintana-locale`, `k.js` appends `&lang=` to the
  iframe, checkout posts `lang`, and `Order.locale` stores it for the order page and email. Browser API calls add
  `X-Iguana-Locale` (`src/lib/kintana-auth.ts`), and `api.middleware.TranslateErrorsMiddleware` translates any JSON
  `{"error": ...}`. The sign-in email takes its language from the `/en/` or `/es/` redirect URL. Door check-in
  follows the staff phone's `Accept-Language`. Ticket types carry `name_es` / `description_es`, snapshotted into the
  order in the customer's language.

### Open mic reservations

Open mics are always free to walk into, but walk-ins can be turned away when full. The room holds 80: 60 seats are
sold as reservations (50 MXN Tuesday en español, 5 USD Wednesday in English), each including one free drink, and 20
stay for walk-ins. A reservation is an ordinary ticket type, so it uses the normal checkout, the per-seat QR codes,
the confirmation email and `/checkin/`; the drink and "arrive when doors open" live in the ticket type description,
which the confirmation email now prints.

`manage.py setup_open_mics [--show-time 20:00 --doors 19:30] [--dry-run]` publishes every upcoming night of the two
series (`Noche de Open Mic - Espanol!`, `Open Mic Night - English!`), sets currency/language, turns off member
benefits, tags them `open-mic`, and creates or updates the reservation type. It is re-runnable and never drops
capacity below seats already booked.

🚨 **Reservations are charged online, so they need Iguana's own Stripe keys, which production does not have yet.**
Kintana charged on its own Stripe account, and without keys checkout answers "Online payment is not available yet".
The command therefore refuses to publish while `stripe_enabled()` is false rather than put up nights nobody can pay
for. `--pay-at-door` is the stopgap: `TicketType.pay_at_door` completes the booking with no charge, records
`Order.pay_at_door_cents`, and the check-in page tells the door what to collect. It is limited to one booking per
email per night and locks the ticket types while booking, because nothing paid up front stops seat hoarding.

The site finds the next bookable night per language by the `open-mic` tag (`src/lib/open-mics.ts`), skipping sold-out
nights, and the home page keeps open mics out of its six event slots.

### Meta ads (Facebook/Instagram)

`scripts/meta-ads.py` (`status`, `campaigns --days N`, `daily --days N`, `pixels`, `pause/resume <id>`) talks to
the Marketing API. It is an operator tool run by hand, so it reads the never-expiring system-user token from
`~/.credentials/meta/iguanacomedy/token`, not `config.py`; no deployed service calls Meta.

| Asset | ID |
| --- | --- |
| Ad account `IGUANA` (MXN, business `IguanaComedy` 681571140696261) | `act_178760798664478` |
| Page `Iguana Comedy Productions` (@iguanacomedy) | `122106930026005410` |
| Instagram @iguanacomedy | `17841461594533193` |
| App `Iguana 2026` / system user `newiguana 2026` | `1616667029816710` |
| Pixel `Ticket Tracking` (used by the Kintana-era site) | `1167556798403907` |
| Pixel `andrew new pixel` (created 2026-09-15, never fired) | `2122037578734069` |

🚨 **A campaign or ad set reading `ACTIVE` is not evidence that it spends.** 31 ad sets report `ACTIVE` while
their `end_time` passed months or years ago, so the UI looks busy and the account has in fact spent nothing
since April 2026. Judge delivery by `end_time` in the future plus non-zero `insights.spend`, which is what
`status` does. The same trap in reverse: `campaigns` only lists campaigns that actually spent in the window.

**No Meta pixel is installed on this site.** `Ticket Tracking` last received an event on 2026-05-17, from the
old Kintana-era site; the Astro site has no `fbq` and the checkout runs in an iframe from `api.iguanacomedy.com`,
so a plain pixel snippet on the marketing pages would not see purchases anyway. Conversion campaigns
(`OUTCOME_SALES`) cannot be optimised or measured until that is fixed, most robustly by sending the purchase
server-side from the Stripe webhook in `api/embed_views.py` via the Conversions API.

### Data outside the repo

`~/iguana-migration/` holds the Kintana CSV export (customer PII), the Wayback Machine mirror, and
`extracted/*.json` + images recovered from the old Framer and Kintana-era sites. Never commit any of it.
`backend/local_data.json` fixtures are gitignored for the same reason.
