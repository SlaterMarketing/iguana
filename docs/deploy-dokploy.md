# Deploy on Dokploy

This site is a **static Astro build** served by **nginx** in Docker. Kintana data is fetched at **build time**, so the `PUBLIC_*` variables must be present when the image builds—not only at runtime.

## 1. Push the repo

Connect your Git provider in Dokploy and select this repository (branch you deploy from, usually `main`).

## 2. Create the application

| Setting | Value |
| -------- | ------ |
| **Type** | Application → **Docker** |
| **Dockerfile** | `Dockerfile` (repo root) |
| **Build context** | `.` |
| **Container port** | `3000` (must match `PORT` in the app env; default is `3000`) |

Enable **Build-time environment variables** for every variable below. In Dokploy this is usually a per-variable toggle such as **“Available at Buildtime”** / **Build Stage** — if it is off, the deploy will succeed but the site will show *“Connect ticketing credentials…”* because Astro bakes data in when the image builds.

Copy the same values you use locally in `.env` (not committed to git).

## 3. Environment variables

Copy from `.env.example` and set in Dokploy:

| Variable | Required | Notes |
| -------- | -------- | ----- |
| `PUBLIC_SITE_URL` | Yes | Live URL, no trailing slash (e.g. `https://iguanacomedy.com`) |
| `PUBLIC_KINTANA_API_KEY` | Yes | Publish key (`kpa_live_…`) |
| `PUBLIC_KINTANA_BASE_URL` | Yes | Kintana host, no trailing slash (e.g. `https://kintana.app`) |
| `PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID` | Yes | Contact form ID |
| `PUBLIC_KINTANA_TRACKER_TOKEN` | No | Tracker `data-token` from Kintana → Websites |

After changing any `PUBLIC_*` value, **redeploy** so the site rebuilds (values are baked into HTML/JS).

## 4. Domain & HTTPS

In Dokploy, attach your domain to this app and turn on TLS (Let’s Encrypt). Point DNS to the server running Dokploy.

## 5. Smoke test locally (optional)

```bash
docker build -t iguana-comedy \
  --build-arg PUBLIC_SITE_URL=https://iguanacomedy.com \
  --build-arg PUBLIC_KINTANA_API_KEY=your_key \
  --build-arg PUBLIC_KINTANA_BASE_URL=https://kintana.app \
  --build-arg PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID=your_form_id \
  .

docker run --rm -p 8080:3000 iguana-comedy
```

Open http://localhost:8080

## Troubleshooting

- **“Connect ticketing credentials so listings can hydrate”** — `PUBLIC_KINTANA_API_KEY` / `PUBLIC_KINTANA_BASE_URL` were missing when the image built. In Dokploy, enable **Available at Buildtime** for every `PUBLIC_*` variable, paste the same values as your local `.env`, then **redeploy** (full rebuild).
- **502 Bad Gateway** — container port must match nginx (`3000` by default, or set `PORT` and the same container port).
- **Empty shows / comedians after deploy** — build ran without Kintana env vars, or API key rejected from the server IP. Check Dokploy build logs for `[Kintana:…]` errors.
- **Contact form broken** — confirm `PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID` was set at build time and the form allows your site origin.
- **Wrong canonical URLs** — set `PUBLIC_SITE_URL` to the final public URL before building.
