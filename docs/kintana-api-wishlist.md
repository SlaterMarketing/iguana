# Kintana API wishlist — from the Iguana Comedy migration

We're rebuilding iguanacomedy.com on `@kintana/sdk` **0.4.1** + the Astro starter.
The numbered sections below are the **original migration ask** — many overlap with
behaviour that now ships; see **[Update — 0.4.1]** before prioritising work.

## Update — `@kintana/sdk` 0.4.1

**Delivered on the SDK / public API:**

- **Events**: `createKintanaClient().listEvents()` supports `limit`, `tourId`,
  `artistSlug`, `from`, `to`, `status`. Payloads expose venue, lineup, headliner,
  `doorsOpen` / `showTime`, descriptions, listing `status`, `language`,
  ticketing type, pricing fields, tags, tours, mobile image, etc. (matches most
  of §1).
- **Artists (comedians)**: `listArtists` / `getArtist` — biography, residency,
  `socials`, `reels`, `upcomingEvents` (implements the spirit of §2; naming is
  `artist` not `comedian`; some fields differ e.g. no typed `countriesOfOrigin[]`
  yet).
- **Venues**: `listVenues` / `getVenue` plus `groupVenuesByCity` exported from
  `@kintana/sdk/locations` (implements much of §3 and the “derive cities from
  venues” path in §4; dedicated city editorial/copy API still absent).
- **Forms**: `getFormSchema` accepts `opts.cache`; upstream documents **~5 min**
  public cache + ETag-safe SSR (closes the ask at the bottom of §9).
- **Tracker**: upstream documents `CustomEvent` hooks incl. `kintana:event_view`,
  `kintana:ticket_click`, `kintana:form_submit`, plus `kintana:pageview`
  (addresses most of §10 except crawlability).

Upstream **explicitly defers until launched** (per package `llms.txt`): generic
marketing `pages` CMS, `/stats`-style KPI aggregates, RRULE / recurrence
resources, and richer embedded form controls (file uploads, selects, branching).

### Still worth tracking for Iguana

- Event **taxonomy** aligned to the old site (“open mic” vs corporate vs hotel)
  if not fully expressible via `tour`, `tags`, or internal ticketing metadata.
- **§4**: First-class `/locations`-style editorial (hero copy per city slug) vs
  only grouped venues.
- **§§5–8** as originally written unless product scope changes.
- **§9**: File / phone / select / conditional fields (schema types still only
  `text` \| `email` \| `textarea` in 0.4.0).
- **§10**: `noscript` or SSR-friendly analytics parity for bots.

---

## 1. Events — richer fields

_Historical ask:_ when `KintanaPublicEvent` was only `{ id, slug, name, date, city,
country, imageUrl, ticketUrl, embedUrl }`. We asked for:

- `venueId` / nested `venue` object (city/country is too coarse for "Zitla Playa"
  vs "another Playa venue")
- `description` (short) + `longDescription` (markdown) for the detail page hero
  and SEO body
- `doorsTime` + `startTime` separately (currently `date` is a single string)
- `endTime` for hotel & corporate shows that book a window
- `lineup`: array of comedian references (id/slug + name) — drives "shows
  featuring X" on a comedian profile
- `headliner`: optional comedian reference, separate from lineup
- `series` / `showType`: enum-ish — `headliner`, `open-mic`, `showcase`,
  `corporate`, `hotel`, `private` (current site segments around these)
- `status`: `on-sale`, `sold-out`, `postponed`, `cancelled`, `past`
- `language`: default `en`, supports future Spanish shows
- `ageRestriction` (e.g. 18+)
- `priceFrom` / `priceCurrency` for listing display
- `tags[]` for free-form filtering

## 2. Comedians — currently no API

_Note: superseded by `artists` in 0.4.0 for core listing/detail; keep for any
still-missing field-level gaps._

`/comedians` and `/comedians/{slug}` are core pages today. Suggested resource:

- `GET /api/public/v1/comedians?limit=N&residency=resident|visiting`
- `GET /api/public/v1/comedians/{idOrSlug}`

Fields:

- `id`, `slug`, `name`, `stageName` (optional)
- `bio` (markdown)
- `headshotUrl`, `gallery[]`
- `homeCity`, `countriesOfOrigin[]`
- `residency`: `resident`, `regular`, `visiting`, `headline-guest`
- `socials`: `instagram`, `tiktok`, `youtube`, `website`
- `reels[]`: `{ title, url, posterUrl }` (YouTube/Vimeo or hosted)
- `upcomingEvents[]` (derived from lineup) — saves us a separate query

## 3. Venues — currently no API

_Note: `listVenues` / `getVenue` exist in 0.4.0; keep for fields like galleries,
directions prose, embeddable maps, parking copy if absent on your venue shapes._

A venue is a real thing (Zitla Playa, etc.) and is more useful than `city`.

- `GET /api/public/v1/venues`
- `GET /api/public/v1/venues/{idOrSlug}`

Fields: `id`, `slug`, `name`, `city`, `country`, `address`, `lat`, `lng`,
`capacity`, `photos[]`, `parkingNotes`, `doorsConvention`, `mapEmbedUrl`,
`upcomingEvents[]`.

## 4. Cities / Locations index

_Navigation grouping is partially addressed via `groupVenuesByCity` from
`@kintana/sdk/locations`; first-class editorial “city pages” remains an ask._

The live site has `/locations` and `/locations/{city}`. We can derive this from
`venues` + `events`, but a first-class resource is cleaner:

- `GET /api/public/v1/locations` → `[{ slug, name, country, heroImageUrl,
  blurb, venueCount, upcomingEventCount }]`
- `GET /api/public/v1/locations/{slug}` → above + `venues[]`, next events.

If Kintana would rather not own city editorial copy, expose the derived list
and we can layer our own blurbs locally.

## 5. Pages / editorial content

About, Comedy For Everyone, Investors, Hotels & Resorts are mostly long-form
copy with images. Either:

- a generic `pages` resource (`{ slug, title, body (markdown), heroImageUrl,
  sections[] }`), or
- a documented convention that these stay in the customer's repo as MDX.

For now we'll plan around in-repo MDX, but a `pages` API would let
non-technical staff edit through Kintana.

## 6. Press / partners

Used on Investors and Hotels & Resorts ("we've performed at…").

- `partners[]`: `{ name, logoUrl, url, category: "hotel" | "venue" | "media" |
  "sponsor" }`
- `pressMentions[]`: `{ outlet, quote, url, publishedAt }`

## 7. Investor metrics

The current Investors page hard-codes "52 events / 4,000 tickets / 80% sell-out
rate in 2025". These should come from a live aggregate:

- `GET /api/public/v1/stats?period=ytd|year:2025` →
  `{ eventsCount, ticketsSold, sellOutRatePct, citiesCount, peakSeasonSuccessPct }`

Otherwise the page goes stale every quarter.

## 8. Recurring series

Open mics happen weekly. Modeling them as N independent events is fine for
ticketing but bad for listings. Suggest:

- `series[]`: `{ slug, name, cadence (RRULE-ish), defaultVenueId, nextEventId,
  upcomingEventIds[] }`

## 9. Form additions

(Cross-reference `docs/kintana-forms-architecture.md`.) Briefly, we need:

- File-upload field type (Perform With Us needs demo reels — upload, not link)
- Phone field type + country code
- Select / multi-select field type (city dropdown on contact form)
- Conditional fields (e.g. "rush fee acknowledged" only when requested date <
  7 days out)
- Server-rendered schema endpoint (`/forms/{id}/schema`) — **✓ documented + wired**
  in 0.4.0 via `cache` option and public cache headers; remaining gaps are richer
  field types and conditional logic.

## 10. Tracker / analytics

The `/_t/k.js` tracker is included via `data-token`. **Partially delivered:** SDK
documents `CustomEvent` hooks incl. those below plus `kintana:pageview`. We'd
still like:

- Clear GA4 bridging examples built on those events (beyond raw `CustomEvent`)
- A `noscript` fallback or server-side hit for SEO crawlers
