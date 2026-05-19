# syntax=docker/dockerfile:1

# Dependencies only — Astro build runs at container start so Dokploy runtime env vars apply.
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS runtime
WORKDIR /app

RUN apk add --no-cache nginx wget

COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json astro.config.mjs tsconfig.json ./
COPY public ./public
COPY src ./src
COPY scripts ./scripts
COPY sitemap.xml ./sitemap.xml
COPY deploy ./deploy

ENV PORT=3000
ENV NODE_ENV=production

RUN chmod +x /app/deploy/docker-entrypoint.sh

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=5 \
  CMD sh -c 'wget -qO- "http://127.0.0.1:${PORT:-3000}/" >/dev/null 2>&1 || exit 1'

ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]
