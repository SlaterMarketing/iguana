#!/bin/sh
set -eu

PORT="${PORT:-3000}"
export PORT

sed "s/__PORT__/${PORT}/g" /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
