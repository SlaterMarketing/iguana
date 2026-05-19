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
| **Port** | `80` |

Enable **Build-time environment variables** (or “Available at Buildtime”) for every variable below. Dokploy should pass the same values into the Docker build `ARG`s.

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

docker run --rm -p 8080:80 iguana-comedy
```

Open http://localhost:8080

## Troubleshooting

- **Empty shows / comedians after deploy** — build ran without Kintana env vars, or API key rejected from the server IP. Check Dokploy build logs for `[Kintana:…]` errors.
- **Contact form broken** — confirm `PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID` was set at build time and the form allows your site origin.
- **Wrong canonical URLs** — set `PUBLIC_SITE_URL` to the final public URL before building.
