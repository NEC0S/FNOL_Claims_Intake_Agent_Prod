#!/bin/sh
set -e

export BACKEND_HOST=$(printf '%s' "$BACKEND_URL" | sed -E 's#^[a-zA-Z]+://##; s#/.*$##')

envsubst '${PORT} ${BACKEND_URL} ${BACKEND_HOST}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'