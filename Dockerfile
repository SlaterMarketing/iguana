# syntax=docker/dockerfile:1

FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# PUBLIC_* vars are inlined at build time — set them in Dokploy (build + runtime).
ARG PUBLIC_SITE_URL=https://iguanacomedy.com
ARG PUBLIC_KINTANA_API_KEY=
ARG PUBLIC_KINTANA_BASE_URL=https://kintana.app
ARG PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID=
ARG PUBLIC_KINTANA_TRACKER_TOKEN=

ENV PUBLIC_SITE_URL=$PUBLIC_SITE_URL \
    PUBLIC_KINTANA_API_KEY=$PUBLIC_KINTANA_API_KEY \
    PUBLIC_KINTANA_BASE_URL=$PUBLIC_KINTANA_BASE_URL \
    PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID=$PUBLIC_KINTANA_SHOW_REQUEST_FORM_ID \
    PUBLIC_KINTANA_TRACKER_TOKEN=$PUBLIC_KINTANA_TRACKER_TOKEN

RUN npm run build:docker

FROM nginx:1.27-alpine AS runtime

# Dokploy / Traefik often forward to 3000; set PORT in the app env to match "Container port".
ENV PORT=3000

COPY deploy/nginx.conf.template /etc/nginx/nginx.conf.template
COPY deploy/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD sh -c 'wget -qO- "http://127.0.0.1:${PORT:-3000}/" >/dev/null 2>&1 || exit 1'

ENTRYPOINT ["/docker-entrypoint.sh"]
