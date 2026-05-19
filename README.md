Website for **Iguana Comedy** on [kintana.app](https://kintana.app), scaffolded from [kintana-astro-starter](https://github.com/kintanaapp/kintana-astro-starter) (Astro 5 + `@kintana/sdk`).

Copy `.env.example` to `.env`, add your **publish key** (`PUBLIC_KINTANA_API_KEY`), **base URL** (your live Kintana hostname, no trailing slash), and **contact form ID**. Set `PUBLIC_KINTANA_TRACKER_TOKEN` to the `data-token` value from Kintana → Websites → external site tracker snippet when you have one—that keeps analytics/forms widgets using the snippet secret instead of repeating the publish key in `<script>`. Then run `npm install` and `npm run dev`.

Static builds call the catalogue at build time, so CI/deploy needs the same variables when generating `/shows/[slug]` routes.

**Dokploy:** see [docs/deploy-dokploy.md](docs/deploy-dokploy.md) — Docker Node server on port **3000**; set `PUBLIC_*` in Environment (runtime).

**Routes shipped:** `/`, `/shows`, `/shows/[slug]`, `/comedians`, `/comedians/[slug]`, `/locations`, `/locations/[city]`, `/about`, `/work-with-us`, `/contact`.

The enquiry page can append `?subject=` so your Kintana form can distinguish intent—add matching field labels there (plaintext only in the UI).
