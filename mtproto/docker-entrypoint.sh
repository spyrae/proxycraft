#!/bin/sh
set -eu

RUNTIME_DIR="${MTPROTO_RUNTIME_DIR:-/app/runtime}"
RUNTIME_CONFIG_PATH="${MTPROTO_RUNTIME_CONFIG_PATH:-${RUNTIME_DIR}/config.py}"
DEFAULT_CONFIG_PATH="${MTPROTO_DEFAULT_CONFIG_PATH:-/opt/mtproto-defaults/config.py}"

mkdir -p "${RUNTIME_DIR}"

if [ ! -f "${RUNTIME_CONFIG_PATH}" ]; then
  cp "${DEFAULT_CONFIG_PATH}" "${RUNTIME_CONFIG_PATH}"
fi

ln -sf "${RUNTIME_CONFIG_PATH}" /app/config.py
chown -R mtproxy:mtproxy "${RUNTIME_DIR}" /app/config.py

exec su -s /bin/sh mtproxy -c "exec python /app/mtprotoproxy.py"
