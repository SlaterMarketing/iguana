# Forms architecture — moving off env-scoped IDs

## Today's pattern (from the Astro starter)

`.env.example` defines:

    PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID=paste-form-id-from-kintana

…and `src/pages/request-a-show.astro` reads
`import.meta.env.PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID` to mount
`<RequestShowIsland />`.

For Iguana Comedy alone, we'd need at minimum:

- Perform With Us
- Private Events / Corporate
- Hotels & Resorts
- Investors
- General Contact

That's five env vars per environment (preview, prod, local). Every new inquiry
type requires a deploy. Form IDs are opaque strings — no human can verify the
env mapping is correct.

## The problem with env-scoped IDs

1. **Coupling**: form identity lives in infra (Vercel env), not in code.
2. **Drift**: prod / preview / local can point at different forms silently.
3. **Discoverability**: there's no way to render "all forms on the site" or to
   know which forms exist without opening the Kintana dashboard.
4. **Onboarding**: every new customer site repeats the same env wiring.

## Recommended pattern — slugs, not IDs

The SDK already exposes `listForms()` returning
`{ id, slug, kind, title }[]`. We propose:

1. Forms are referenced everywhere in code by **slug**, never by ID.
   - `<KintanaForm slug="perform-with-us" />`
   - `<KintanaForm slug="private-events" />`
2. The SDK resolves slug → id once (server-side, cached) using `listForms()`.
3. `.env` keeps only `PUBLIC_KINTANA_API_KEY` and `PUBLIC_KINTANA_BASE_URL`.
   Form provisioning happens entirely inside Kintana.
4. Reserved slugs (`contact`, `perform-with-us`, `private-events`,
   `hotels-and-resorts`, `investors`) get a `kind` enum on the Kintana side so
   the SDK can render sensible defaults even if a customer hasn't created the
   form yet.

### Suggested SDK addition

    client.getFormBySlug(slug: string): Promise<KintanaPublicFormSchema>

…so consumers never touch IDs. (`submitForm` could accept either, with slug
preferred.)

### Suggested React helper

    import { KintanaForm } from "@kintana/sdk/react";

    <KintanaForm slug="perform-with-us" />

Internally: resolves slug, fetches schema, renders, submits. No env wiring, no
copy/paste of IDs.

## Should form IDs ever be env-scoped?

Only for one case: **A/B testing or staging form variants** where the same
slug must point at different forms per environment. Even then, an override map
is cleaner than a per-form variable:

    KINTANA_FORM_OVERRIDES='{"contact":"frm_test_xyz"}'

…parsed once at boot. This keeps the default path slug-only.

## Migration

For the starter repo:

- Delete `PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID` from `.env.example`.
- Change `RequestShowIsland` props from `formId` to `slug="request-a-show"`.
- Update `CLAUDE.md` to recommend slug-based references.

For Iguana Comedy specifically, every inquiry page references a stable slug;
adding "Brand partnerships" later is a Kintana-side change, not a deploy.

## File uploads

Per Iguana's brief, "Perform With Us" needs demo reel uploads. The current
form schema only supports `text | email | textarea`. We're treating
`file-upload` as a hard requirement before that page can ship — see API
wishlist §9.
