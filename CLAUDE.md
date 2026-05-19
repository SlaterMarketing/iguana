## Astro-specific notes

Public env vars MUST use Astro’s `PUBLIC_` prefix (not `NEXT_PUBLIC_`). Anything referencing `createKintanaClient` belongs in `.astro` frontmatter so it executes on the server.

Optional **`KINTANA_SECRET_API_KEY`** (`kpa_secret_…`) is loaded in [`src/lib/kintana-env.ts`](src/lib/kintana-env.ts) (`secretApiKey`, `hasWorkspaceSecret`). Prefer **`createKintanaClientFromEnv()`** for server-side calls that should use the secret when present — never prefix it with `PUBLIC_` or pass it to hydrated islands (see `@kintana/sdk` README).

## Layout

[`src/layouts/Base.astro`](src/layouts/Base.astro) owns global chrome (`Header`, `Footer`) + tracker `<script>`. Narrow pages pass `narrow` for contained widths; full-bleed marketing pages omit it.

| Route                     | Technique                                                                                       |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| `/`                       | Homepage hero/stats leveraging `client.listEvents` + `client.listArtists`                      |
| `/events`                 | `listEvents` grouped via [`src/lib/events.ts`](src/lib/events.ts)                              |
| `/events/[slug]`          | `getEvent(slug)` + `getStaticPaths()` seeded from downstream events                             |
| `/comedians`              | `listArtists()`                                                                                 |
| `/comedians/[slug]`       | `getArtist(slug)` + `getStaticPaths()` sourced from downstream artists                          |
| `/locations`              | `listVenues()` + `groupVenuesByCity` from `@kintana/sdk/locations`                               |
| `/locations/[city]`       | City blurbs [`src/content/city-blurbs.ts`](src/content/city-blurbs.ts) layered on grouped data |
| `/about`, `/work-with-us` | MDX routed through [`src/layouts/WideMarkdown.astro`](src/layouts/WideMarkdown.astro)           |
| `/contact`                | `<ContactFormIsland client:load />`; `?subject=` mirrors an optional plaintext `subject` field  |

## SDK reminders

- `listEvents` accepts `{ limit, tourId, artistSlug, from, to, status }`; `listArtists({ limit })` powers directories.
- `getFormSchema` accepts `{ cache }`; `ContactFormIsland` caches through `force-cache`.
- Hydrate React only where hooks are unavoidable (today: contact form island).
