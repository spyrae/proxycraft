#!/bin/sh
set -eu

PIDFILE="${HAPROXY_PIDFILE:-/var/run/haproxy.pid}"
CERT_FILE="${HAPROXY_SSL_CERT_PATH:-/etc/haproxy/ssl/proxy.pem}"

[ -s "$CERT_FILE" ]
[ -s "$PIDFILE" ]

pid="$(cat "$PIDFILE")"
kill -0 "$pid" 2>/dev/null

nc -z 127.0.0.1 587
nc -z 127.0.0.1 7777
