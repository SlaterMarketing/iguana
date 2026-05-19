#!/bin/sh
set -eu

PORT="${PORT:-3000}"
export PORT

echo "[iguana] Preparing environment for Astro build..."
node /app/scripts/materialize-env.mjs

echo "[iguana] Building static site..."
if node /app/scripts/check-kintana-env.mjs; then
  npm run build
else
  echo "[iguana] Warning: Kintana credentials missing — check Dokploy Environment (KEY=value per line)."
  npm run build
fi

rm -rf /usr/share/nginx/html/*
mkdir -p /usr/share/nginx/html
cp -r /app/dist/. /usr/share/nginx/html/

sed "s/__PORT__/${PORT}/g" /app/deploy/nginx.conf.template > /etc/nginx/conf.d/default.conf

echo "[iguana] Serving on port ${PORT}"
exec nginx -g "daemon off;"
