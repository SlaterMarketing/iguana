#!/bin/sh
set -eu

PORT="${PORT:-3000}"
export PORT

echo "[iguana] Building static site with container environment..."
if node /app/scripts/check-kintana-env.mjs; then
  :
else
  echo "[iguana] Warning: missing Kintana env — continuing; listings may be empty."
fi

npm run build

rm -rf /usr/share/nginx/html/*
mkdir -p /usr/share/nginx/html
cp -r /app/dist/. /usr/share/nginx/html/

sed "s/__PORT__/${PORT}/g" /app/deploy/nginx.conf.template > /etc/nginx/conf.d/default.conf

echo "[iguana] Serving on port ${PORT}"
exec nginx -g "daemon off;"
