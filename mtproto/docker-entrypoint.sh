#!/bin/sh
set -eu

RUNTIME_DIR="${MTPROTO_RUNTIME_DIR:-/app/runtime}"
RUNTIME_CONFIG_PATH="${MTPROTO_RUNTIME_CONFIG_PATH:-${RUNTIME_DIR}/config.py}"
DEFAULT_CONFIG_PATH="${MTPROTO_DEFAULT_CONFIG_PATH:-/opt/mtproto-defaults/config.py}"
export RUNTIME_CONFIG_PATH

mkdir -p "${RUNTIME_DIR}"

if [ ! -f "${RUNTIME_CONFIG_PATH}" ]; then
  cp "${DEFAULT_CONFIG_PATH}" "${RUNTIME_CONFIG_PATH}"
fi

export MTPROTO_PORT="${MTPROTO_PORT:-8444}"
export MTPROTO_TLS_DOMAIN="${MTPROTO_TLS_DOMAIN:-www.cloudflare.com}"
export MTPROTO_MASK_HOST="${MTPROTO_MASK_HOST:-www.cloudflare.com}"
export MTPROTO_MASK_PORT="${MTPROTO_MASK_PORT:-443}"
export MTPROTO_FAST_MODE="${MTPROTO_FAST_MODE:-true}"

python - <<'PY'
from pathlib import Path
import os
import re

config_path = Path(os.environ["RUNTIME_CONFIG_PATH"])
content = config_path.read_text(encoding="utf-8")

replacements = {
    "PORT": os.environ["MTPROTO_PORT"],
    "TLS_DOMAIN": repr(os.environ["MTPROTO_TLS_DOMAIN"]),
    "MASK_HOST": repr(os.environ["MTPROTO_MASK_HOST"]),
    "MASK_PORT": os.environ["MTPROTO_MASK_PORT"],
    "FAST_MODE": "True" if os.environ["MTPROTO_FAST_MODE"].lower() in {"1", "true", "yes", "on"} else "False",
}

for key, value in replacements.items():
    pattern = rf"^{key}\s*=.*$"
    replacement = f"{key} = {value}"
    if re.search(pattern, content, flags=re.MULTILINE):
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    else:
        content = f"{replacement}\n{content}"

config_path.write_text(content, encoding="utf-8")
PY

ln -sf "${RUNTIME_CONFIG_PATH}" /app/config.py
chown -R mtproxy:mtproxy "${RUNTIME_DIR}" /app/config.py

exec su -s /bin/sh mtproxy -c "exec python /app/mtprotoproxy.py"
