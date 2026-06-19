# Kintana headless submission endpoints

Custom sites submit to Kintana by **endpoint slug** — no form IDs, no schema fetch.

## Env

```bash
PUBLIC_KINTANA_API_KEY=kpa_live_…
PUBLIC_KINTANA_BASE_URL=https://kintana.app
KINTANA_SECRET_API_KEY=kpa_secret_…  # setup:endpoints only
```

## Submit from your site

```ts
await client.submitEndpoint("contact", {
  email: "fan@example.com",
  fields: { firstName: "Taylor", lastName: "Fan", message: "Book us!" },
  context: { city: "London", country: "United Kingdom" }, // optional page metadata
});
```

React: `useKintanaSubmit("contact")` from `@kintana/sdk/react`.

## Provision endpoints

```bash
npm run setup:endpoints
```

Creates or updates endpoints in Kintana (show request, newsletter, etc.) with stable slugs.

## Multiple inquiry types (Iguana-style)

Reference endpoints by slug in code — no env per form:

- `<ShowRequestForm endpointSlug="perform-with-us" />`
- `<ShowRequestForm endpointSlug="hotels-and-resorts" />`

Add new endpoints in Kintana; use the slug in your page component.
