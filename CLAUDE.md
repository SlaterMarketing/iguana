# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Iguana Comedy (stand-up promoter, Quintana Roo, Mexico). Two apps in one repo: a bilingual **Astro 5 SSR site**
(repo root) and a **Django backend** (`backend/`) that replaced the Kintana SaaS the site was originally built on.
Repo is `SlaterMarketing/iguana` (public, client-owned). Backend, deploy and migration work lives on branch
`backend-django`, which has not been pushed: ask before pushing anywhere.

## Commands

```bash
# End to end (needs the backend on :8000 and the BUILT site on :4321, not the dev server: the account and
# checkout islands are React, and a stale Vite dep cache silently breaks hydration)
npm run build:node && node dist/server/entry.mjs &   # port 4321, env from .env
node tests/account-flow.mjs                          # register, code sign-in, magic link
node tests/reserve-flow.mjs                          # reserve a seat through the real checkout iframe

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

**Always deploy.** A change is finished when it is live on the VPS and checked there, not when it is committed:
the club is trading off this site, so nothing of value happens until production has it. Backend data changes
(a new event, seeded copy) also need their management command run on the server, because the deploy only ships
code. Anything that genuinely cannot be deployed, such as a Stripe dashboard setting, gets said out loud.

One VPS (VPS.org `free` account, 38.86.78.36, user `iguana`, creds `~/.credentials/vpsorg/iguanacomedy/`).
nginx fronts supervisor programs `iguana:iguana-web` (Node, :3000) and `iguana:iguana-api` (gunicorn, :8001);
Postgres `iguana`. `iguanacomedy.com` is canonical (DNS on Cloudflare, records must stay DNS-only: proxied records
pointing at Cloudflare IPs caused the old Error 1000); `iguanacomedy.mx` 301s to it; API at
`api.iguanacomedy.com` (and `api.iguanacomedy.mx`). Admin: `https://api.iguanacomedy.com/admin/`.

- `ansible/files/nginx.conf.j2` renders TLS blocks only for certificates that exist (`cert_sets`), so redeploys
  never strip HTTPS. nginx is 1.24: use `listen 443 ssl http2`, not `http2 on`.
- Code is rsynced from the local checkout (not git-pulled). `backend/media/` syncs add-only so server uploads survive.
  To deploy exactly a commit while the working tree has other changes, deploy from a clean worktree:
  `git worktree add --detach /tmp/x HEAD && ansible-playbook deploy.yml -e repo_root=/tmp/x -e media_src=$PWD/../backend/media`.
  🚨 Never make `backend/media` a symlink in the source tree. On 2026-09-17 that slipped past the old
  `--exclude=backend/media/` (a trailing slash matches directories only), rsync `--delete` replaced the server's media
  folder with a dangling symlink, and every event image returned 404 for about 4 minutes until it was restored from
  the local copy. The exclude is now anchored and type-agnostic (`/backend/media`), and deploy.yml asserts both the
  server path and `media_src` are real directories before syncing.
- Mail (`ansible/mail.yml`): Postfix + OpenDKIM for every zone in `mail_zones` (`iguanacomedy.mx` and
  `iguanacomedy.com`, each with its own DKIM key under selector `mail`), one mail host `mail.iguanacomedy.mx`
  because the PTR points there. `mail_human_aliases` (hello, info, bills, andrew, john, will, will.slater) deliver to the local
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

### Newsletter, city alerts and who signs up from where

- The home hero's bottom-left is a newsletter sign-up (`NewsletterSignup.astro`, form endpoint slug `newsletter`,
  intent `newsletter`). Subscribers join the `Newsletter` contact list; there is no alert email per sign-up.
- A city page, or `/events/?city=`, with nothing coming up (any city except Playa del Carmen) shows
  `NoEventsNearby.astro`: travel time to the club (`src/content/playa-travel.ts`), links to Playa shows, the open
  mics and directions, and a "tell me when there's a show in <city>" sign-up that also joins `City alerts: <City>`.
  Those lists are who to email when a show is booked in that city.
- Every form sign-up and every booking records who and where (`backend/crm/geo.py`): site language, browser
  language, time zone and IP location (country, region, city). It lands on the contact (`locale`, `geo_*`,
  `time_zone`, `last_ip`), in `FormSubmission.context["visitor"]` and in `Order.attribution["visitor"]`. The real
  IP comes from nginx's `X-Real-IP`, trusted only when the request came from the local proxy (before this, every
  submission recorded 127.0.0.1).
- IP location uses DB-IP "IP to City Lite" (CC BY 4.0) at `geoip_db` (`/var/lib/iguana/dbip-city-lite.mmdb`).
  `deploy.yml` downloads it when missing and installs a monthly cron (`iguana-geoip-refresh`, logs to
  `journalctl -t iguana-geoip`); `geo.py` reopens the file when it changes, so no restart. A missing file only logs a
  warning: sign-ups and checkout never fail over it.
- City pages used to list a city's oldest past shows under "Upcoming in <city>" (no `from` filter); both loaders in
  `src/lib/locations-data.ts` now ask for today onward (`todayInCancun()`) and drop `past`.

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

**Conversion tracking: the backend reports the sale, the pixel only reports the visit.** Checkout is an iframe
served from `api.iguanacomedy.com`, so a pixel on the marketing pages can never see a purchase. `crm/meta_capi.py`
sends `Purchase` (from `complete_order`) and `InitiateCheckout` (from `checkout_start`) to pixel
`2122037578734069` over the Conversions API; `src/components/MetaPixel.astro` sends only `PageView` and
`ViewContent`. One sender per event, so there is no deduplication to get wrong and the money events survive an
ad blocker. Keys are `META_PIXEL_ID` / `META_CAPI_TOKEN` in `config.py` and `PUBLIC_META_PIXEL_ID` in `.env`.

🔑 **Matching is what decides whether a sale is attributed at all, and `_fbp`/`_fbc` belong to the SITE origin,
not the iframe.** `k.js` reads both cookies, rebuilds `_fbc` from `fbclid` when the pixel was blocked before it
could write one, and posts them as attribution; `checkout_start` stores them plus the User-Agent on the order and
`sales/ad_reporting.py` reads them back. A production order carries ten match fields
(`em fn ln ct st country client_ip_address client_user_agent fbp fbc`). Never report a sale without them: an
unattributed sale teaches the algorithm the ad did not work.

Nothing in that path may cost a booking. Every send is queued `on_commit`, runs on a daemon thread and swallows
its failures; `api.tests.MetaConversionTests` asserts a sale still completes with the Graph API throwing.

**A pixel's history cannot be imported into another pixel.** The Conversions API refuses any event with an
`event_time` older than seven days, so there is nothing to backfill, and `Ticket Tracking`'s last event (2026-05-17)
is outside every window Meta optimises on anyway. The one thing that *can* be imported is the customer list:
`scripts/meta-audiences.py build [--lookalike]` hashes the CRM **on the production box** (only hashes leave it)
and pushes it as a Custom Audience.
⚠ It needs the Custom Audience Terms accepted once, by hand, at
`business.facebook.com/ads/manage/customaudiences/tos/?act=178760798664478`. There is no API for that, and until
it is accepted every create returns 400.

**The weekly open mic campaigns.** `scripts/meta-openmic-campaigns.py` (`plan`, `apply [--live]`, `status`,
`pause`) builds two campaigns per night and is idempotent: it matches on name and updates rather than duplicating,
so re-running after a copy or budget change is safe. Per night, 1,000 MXN a week: a `OUTCOME_SALES` ad set at 100
MXN/day optimised for `Purchase` against the pixel, and a `OUTCOME_TRAFFIC` ad set at 43 MXN/day optimised for
landing page views. The split is deliberate. A reservation is 50 MXN with a drink included, so at this account's
historic 55 to 220 MXN cost per purchase the conversion ads cost more per head than they collect: they pay back at
the bar, and the cheap traffic ads fill the 20 walk-in seats and seed the pixel at the same time.

Targeting comes from what actually worked here: Playa del Carmen (geo key `1540930`), `home` **and** `recent` so
tourists are not excluded, 18 to 65, interest `6003273904571` "Comedia stand up" on the conversion ad sets and
nothing on the reach ad sets. English night adds locales `[6, 24]`.

🚨 **Ads point at `/open-mic/`, never at an event page.** Event URLs carry their date
(`/events/playa-del-carmen-2026-09-22/`), so a weekly campaign aimed at one needs rewriting every Tuesday and
spends on a dead show in between. `src/components/OpenMicPage.astro` asks the API for the next bookable night in
each language on every request and carries both checkouts inline. Use the apex domain: `www.` 301s, and a redirect
costs clicks.
| Campaign | ID |
| --- | --- |
| Open mic Spanish · reservations / ad set | `120250125973220182` / `120250125973580182` |
| Open mic Spanish · local reach / ad set | `120250125990540182` / `120250126057270182` |
| Open mic English · reservations / ad set | `120250126057820182` / `120250126057990182` |
| Open mic English · local reach / ad set | `120250126062910182` / `120250126063000182` |

🚨 **The Meta app must be in LIVE mode or no ad creative can be made at all.** App `Iguana 2026`
(`1616667029816710`) is the business's only app, and while it is in Development mode every POST to
`/adcreatives` returns 400 "se creó con una app que se encuentra en modo de desarrollo", with or without
Instagram on the creative. Campaigns, ad sets, video and image uploads all succeed, so the account looks built
and delivers nothing. Toggle it at `developers.facebook.com/apps/1616667029816710/settings/basic/`, then re-run
`apply --live`. An ad set with no ads cannot spend, so leaving the structure ACTIVE meanwhile is safe.

⚠ Creating a campaign without CBO now requires `is_adset_budget_sharing_enabled`; Meta 400s without it.
⚠ **A city radius under 17km is refused** ("el radio geográfico no se encuentra dentro de los límites"), so the
walk-in ad set cannot be drawn tighter than that.
⚠ **Read every edge once per run.** Paging the account for each lookup trips the ad account rate limit partway
through and leaves half the structure built; the builder caches listings and backs off on codes
`{4, 17, 32, 613}` / subcodes `{2446079, 1487742}`, because that limit clears only by waiting.
⚠ No `end_time` on any ad set, on purpose. 31 ad sets on this account say ACTIVE with a schedule that ended
months ago, which is what makes the UI look busy while the account spends nothing.

**Posting to Facebook and Instagram.** `scripts/meta-social.py` (same token, stdlib only) has `whoami` (scopes,
Page and IG visibility, Page tasks, IG publishing quota), `recent` (last 5 Page posts and IG media),
`draft <slug> [--lang en|es|both] [--image URL]` and `post <slug> --to facebook|instagram|both --confirm`. It pulls
the event from the public API (key from `--api-key`, `IGUANA_PUBLIC_API_KEY`, else over ssh from prod `config.py`),
builds brand-voice captions (Spanish block first for `language: es`, no dashes, Instagram says "link in bio"
because the IG bio links to `/events`), and blocks on: no image, image not a public https JPEG/PNG, aspect ratio
outside 4:5 to 1.91:1, event page not 200, event past or cancelled. Without `--confirm`, `post` only drafts and
exits 2. Facebook posts go through `/{page}/photos` with a Page token derived at run time (never printed);
Instagram through `/media`, a `status_code` poll, then `/media_publish`. Weekly open mics have no image and no
`showTime` in the data, so they cannot be posted until one is set (or `--image` is passed); WebP is refused.
Tests: `python3 -m unittest discover -s scripts/tests`.

### Reading the mail the server keeps

Every human alias delivers to the local `inbox` user **as well as** forwarding, so the box is the copy that
survives a rejected forward. `/usr/local/bin/iguana-mail` (installed by `mail.yml`, read only) reads it:
`iguana-mail`, `iguana-mail show 37`, `iguana-mail search reservation`, `iguana-mail list --box dmarc`.
Worth checking when a customer says they wrote in, or when Stripe/Google send an account notice: a Stripe
"acción requerida" about an overdue ID check was sitting there unread while the API only said
`payouts_enabled: false`.

🚨 **Every newsletter sign-up this site had ever received was ONE BOT, and nothing about the requests could
tell it from a person.** All 59, found 2026-09-21: `timeZone: Europe/Moscow` on every one, `page: /en/`,
`browserLanguage: en-US`, arriving through Tor exits in DE/SE/US/NL, paced at a median 63-minute gap and never
under four so the rate never looked like a burst. The addresses were scraped and belonged to real strangers at
universities and companies. The Monday cron was hours from making this domain's FIRST bulk send to all of
them, which would have taken the 626 real contacts' deliverability down with it.
🔑 **The payload is not a discriminator: the bot sends exactly what the real form sends.** The gate is the one
thing it cannot do, which is read the mail. `crm/optin.py` holds the signed confirm token (its own salt, so an
unsubscribe link can never re-subscribe someone who used it to leave); a sign-up creates the contact
**unsubscribed and on no list**, sends one confirmation, and only `/newsletter/confirm/<token>` makes it
mailable. `api.tests.NewsletterOptInTests` covers it.
⚠ **Do NOT key "already confirmed" on `Contact.subscribed`** — the model defaults it to `True`, so every brand
new contact reads as confirmed and the gate silently does nothing. That was the first version of this. Key it
on whether `get_or_create` actually created the row, and never downgrade an existing subscriber who signs up
again.
⚠ **A missing `visitorKey` proves nothing**: the real newsletter form has never sent one, so "0 of 59 carry a
visitor key" is not evidence of automation. The uniform timezone was.
⚠ **The contact form was being farmed too** (15 random-string submissions in 3 days, each one emailing
`hello@`). `catalog/spam.py` is a honeypot plus a check that free text is not one unbroken run of letters and
digits; a dropped submission gets the SAME success response as a real one, because naming the gate teaches the
bot to pass it. The rows were never the cost: the cost is the owner learning to ignore the alert that a real
enquiry arrives in.

🚨 **A migration that adds a NOT NULL column 500s live checkouts until the workers reload, and the deploy used
to leave ten minutes between the two.** `migrate` ran at line 163 and the gunicorn HUP sat down beside the site
restart, on the far side of `npm install` and the Astro build. In between, the database has the new schema and
the workers are still running the old code, which inserts without the column. Measured 2026-09-21 on
`OrderItem.is_addon`: two `POST /api/checkout/<id>/start` from a Facebook in-app browser on Android, both 500,
both a real ad click that did not become a reservation. **Nothing is written on that path, so the DB cannot show
you the loss and neither can an order count** — the only trace is `/var/log/iguana/api.out.log`, and the
traceback in `api.err.log` carries no timestamp of its own, only the nearest gunicorn line.
Two fixes, both in place: the API now reloads **directly after the migration**, before the long site build; and
`0006_orderitem_is_addon_db_default` restores the database default Django drops, so an insert from an old worker
gets `false` rather than an `IntegrityError`. **Give any new NOT NULL column a DB default in a follow-up
migration** (Postgres only — SQLite cannot ALTER it and does not need to).

🚨 **The deploy used to break live traffic twice over, and both were invisible to every log check.** Gunicorn
was hard-restarted, so the checkout iframe served **502 inside the ad landing page** for the ~2s window; it is
now a graceful `supervisorctl signal HUP`, which keeps the listening socket, and only a dependency change
falls back to a restart. Worse, the site was rebuilt **in place**: the Node adapter resolves Astro route
modules lazily, so every route the running process had not yet imported threw `ERR_MODULE_NOT_FOUND` until the
restart (`/en/open-mic/` 500'd for a minute on 2026-09-21 with ads pointed at it). It now builds into
`dist.next`, asserts that build produced a `server/entry.mjs`, and renames; `dist.old` is the rollback. The
play then polls the site and the checkout before finishing.

🚨 **`/var/mail/inbox` is 0600 `inbox:mail` and the deploy user was in neither group, so `iguana-mail` read
NOTHING and a check reported the mailbox as a clean channel.** An unread channel is not an empty one. `mail.yml`
now puts `deploy_user` in `mail` and sets the boxes 0640. Reading it is what found the Stripe "acción
requerida" thread and the performer enquiry that had waited a month.

🚨 **The weekly newsletter has never sent a single message, and it reported nothing.** `send_marketing` built
each message with a connection and then called `message.send(fail_silently=True)`. Django refuses that
combination and raises `TypeError: fail_silently cannot be used with a connection` on the FIRST recipient, so
every Monday the cron woke up, resolved its 627 subscribers, wrote the campaign row and died having delivered
none of them. The only evidence anywhere was a traceback under `journalctl -t iguana-newsletter`; the campaign
row exists with zero recipients, which looks like "nobody was due" rather than "it crashed".
Fixed 2026-09-22: the tolerance belongs on the connection, `get_connection(fail_silently=True)`.
**Enabled 2026-09-22** (`newsletter_enabled: true` in `group_vars/all`, which `deploy.yml` reads; set it to
false to pause without editing a crontab by hand). Mondays 14:00 UTC, 09:00 in Playa, ~645 recipients paced
0.2s apart, about two minutes inside a 30m timeout. Before the first live run: one was sent to hello@ by hand
and read, and every link in it was opened in a browser.
🔑 **Each open mic line pins `night` and `date`.** The lander offers four dates and defaults to the next one,
so an unpinned link in a Monday mail naming Wednesday opened Tuesday: the reader books, gets a confirmation
and finds out at the door. Verified per-link, not per-page.
Before this the domain's only bulk send was the "Club Opening" campaign on 2026-09-14 to 722 addresses, which
is what people remember when they say emails went out.

Marketing mail must go through `crm.mail.send_marketing` (or `manage.py send_newsletter`, a dry run without
`--send`), which drops unsubscribed contacts and attaches the unsubscribe footer and `List-Unsubscribe` headers
itself. `crm/unsubscribe.py` signs the per-address token; `/unsubscribe/<token>` serves the bilingual page and
accepts Gmail's cookie-less one-click POST. Receipts and sign-in codes deliberately carry no unsubscribe link.

### Data outside the repo

`~/iguana-migration/` holds the Kintana CSV export (customer PII), the Wayback Machine mirror, and
`extracted/*.json` + images recovered from the old Framer and Kintana-era sites. Never commit any of it.
`backend/local_data.json` fixtures are gitignored for the same reason.
