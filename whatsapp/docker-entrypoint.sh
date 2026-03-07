#!/bin/sh
set -eu

CONFIG_PATH="${HAPROXY_CONFIG_PATH:-/usr/local/etc/haproxy/haproxy.cfg}"
PIDFILE="${HAPROXY_PIDFILE:-/var/run/haproxy.pid}"
CERT_DIR="${HAPROXY_CERT_DIR:-/etc/haproxy/ssl}"
CERT_FILE="${HAPROXY_SSL_CERT_PATH:-${CERT_DIR}/proxy.pem}"
CERT_DAYS="${SHOP_WHATSAPP_TLS_CERT_DAYS:-3650}"
TLS_CN="${SHOP_WHATSAPP_TLS_CN:-${SHOP_WHATSAPP_HOST:-proxy.proxycraft.tech}}"
OPENSSL_CONFIG="/tmp/whatsapp-openssl.cnf"
DEFAULT_CONFIG_PATH="${HAPROXY_DEFAULT_CONFIG_PATH:-/opt/proxycraft-defaults/haproxy.cfg}"

mkdir -p "$CERT_DIR"
mkdir -p "$(dirname "$CONFIG_PATH")"

write_openssl_config() {
  cat >"$OPENSSL_CONFIG" <<EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = ${TLS_CN}

[v3_req]
subjectAltName = DNS:${TLS_CN}
extendedKeyUsage = serverAuth
EOF
}

ensure_certificate() {
  if [ -s "$CERT_FILE" ]; then
    return 0
  fi

  write_openssl_config
  openssl req \
    -x509 \
    -nodes \
    -newkey rsa:2048 \
    -days "$CERT_DAYS" \
    -keyout "${CERT_DIR}/proxy.key" \
    -out "${CERT_DIR}/proxy.crt" \
    -config "$OPENSSL_CONFIG"
  cat "${CERT_DIR}/proxy.key" "${CERT_DIR}/proxy.crt" >"$CERT_FILE"
  chmod 600 "${CERT_DIR}/proxy.key" "${CERT_DIR}/proxy.crt" "$CERT_FILE"
  rm -f "$OPENSSL_CONFIG"
}

ensure_config() {
  if [ -s "$CONFIG_PATH" ]; then
    return 0
  fi

  if [ ! -s "$DEFAULT_CONFIG_PATH" ]; then
    echo "Default HAProxy config is missing: $DEFAULT_CONFIG_PATH" >&2
    exit 1
  fi

  cp "$DEFAULT_CONFIG_PATH" "$CONFIG_PATH"
}

validate_config() {
  haproxy -c -f "$CONFIG_PATH"
}

start_haproxy() {
  haproxy -D -p "$PIDFILE" -f "$CONFIG_PATH"
}

reload_haproxy() {
  validate_config

  if [ ! -s "$PIDFILE" ]; then
    echo "HAProxy pidfile not found, starting a fresh instance" >&2
    start_haproxy
    return 0
  fi

  old_pid="$(cat "$PIDFILE")"
  haproxy -D -p "$PIDFILE" -f "$CONFIG_PATH" -sf "$old_pid"
}

stop_haproxy() {
  if [ -s "$PIDFILE" ]; then
    kill -TERM "$(cat "$PIDFILE")" 2>/dev/null || true
  fi
}

handle_hup() {
  reload_haproxy || {
    echo "HAProxy reload failed, keeping the previous config" >&2
    return 1
  }
}

trap 'handle_hup' HUP
trap 'stop_haproxy; exit 0' INT TERM

ensure_config
ensure_certificate
validate_config
start_haproxy

while true; do
  if [ ! -s "$PIDFILE" ]; then
    echo "HAProxy pidfile disappeared" >&2
    exit 1
  fi

  current_pid="$(cat "$PIDFILE")"
  if ! kill -0 "$current_pid" 2>/dev/null; then
    echo "HAProxy process ${current_pid} is not running" >&2
    exit 1
  fi

  sleep 5
done
