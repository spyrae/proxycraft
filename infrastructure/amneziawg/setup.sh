#!/bin/bash
# AmneziaWG initial setup — generates server keys and awg0.conf
# Run once on the server before starting docker-compose
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/config"
PEERS_DIR="${SCRIPT_DIR}/peers"

# Load .env
if [ -f "${SCRIPT_DIR}/.env" ]; then
  set -a
  source "${SCRIPT_DIR}/.env"
  set +a
else
  echo "ERROR: .env file not found. Copy .env.example to .env and configure."
  exit 1
fi

# Defaults
AWG_LISTEN_PORT="${AWG_LISTEN_PORT:-51820}"
AWG_SERVER_IP="${AWG_SERVER_IP:-10.10.0.1}"
AWG_SUBNET="${AWG_SUBNET:-10.10.0.0/24}"

# AmneziaWG obfuscation defaults
AWG_JUNK_PACKET_COUNT="${AWG_JUNK_PACKET_COUNT:-4}"
AWG_JUNK_PACKET_MIN_SIZE="${AWG_JUNK_PACKET_MIN_SIZE:-40}"
AWG_JUNK_PACKET_MAX_SIZE="${AWG_JUNK_PACKET_MAX_SIZE:-70}"
AWG_INIT_PACKET_JUNK_SIZE="${AWG_INIT_PACKET_JUNK_SIZE:-0}"
AWG_RESPONSE_PACKET_JUNK_SIZE="${AWG_RESPONSE_PACKET_JUNK_SIZE:-0}"
AWG_INIT_PACKET_MAGIC_HEADER="${AWG_INIT_PACKET_MAGIC_HEADER:-1}"
AWG_RESPONSE_PACKET_MAGIC_HEADER="${AWG_RESPONSE_PACKET_MAGIC_HEADER:-2}"
AWG_UNDER_LOAD_PACKET_MAGIC_HEADER="${AWG_UNDER_LOAD_PACKET_MAGIC_HEADER:-3}"
AWG_TRANSPORT_PACKET_MAGIC_HEADER="${AWG_TRANSPORT_PACKET_MAGIC_HEADER:-4}"

mkdir -p "${CONFIG_DIR}" "${PEERS_DIR}"

# Generate server keys if missing
if [ ! -f "${CONFIG_DIR}/server_private.key" ]; then
  echo "Generating server keys..."
  wg genkey | tee "${CONFIG_DIR}/server_private.key" | wg pubkey > "${CONFIG_DIR}/server_public.key"
  chmod 600 "${CONFIG_DIR}/server_private.key"
  echo "Server public key: $(cat "${CONFIG_DIR}/server_public.key")"
else
  echo "Server keys already exist, skipping generation."
fi

SERVER_PRIVATE_KEY="$(cat "${CONFIG_DIR}/server_private.key")"

# Detect default network interface
DEFAULT_IFACE="$(ip route | awk '/default/ {print $5; exit}')"
if [ -z "${DEFAULT_IFACE}" ]; then
  echo "WARNING: Could not detect default network interface, using eth0"
  DEFAULT_IFACE="eth0"
fi

# Generate awg0.conf
cat > "${CONFIG_DIR}/awg0.conf" <<EOF
[Interface]
Address = ${AWG_SERVER_IP}/24
ListenPort = ${AWG_LISTEN_PORT}
PrivateKey = ${SERVER_PRIVATE_KEY}

# AmneziaWG obfuscation parameters
Jc = ${AWG_JUNK_PACKET_COUNT}
Jmin = ${AWG_JUNK_PACKET_MIN_SIZE}
Jmax = ${AWG_JUNK_PACKET_MAX_SIZE}
S1 = ${AWG_INIT_PACKET_JUNK_SIZE}
S2 = ${AWG_RESPONSE_PACKET_JUNK_SIZE}
H1 = ${AWG_INIT_PACKET_MAGIC_HEADER}
H2 = ${AWG_RESPONSE_PACKET_MAGIC_HEADER}
H3 = ${AWG_UNDER_LOAD_PACKET_MAGIC_HEADER}
H4 = ${AWG_TRANSPORT_PACKET_MAGIC_HEADER}

# NAT and forwarding
PostUp = iptables -A FORWARD -i awg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o ${DEFAULT_IFACE} -j MASQUERADE
PostDown = iptables -D FORWARD -i awg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o ${DEFAULT_IFACE} -j MASQUERADE

# Peers are added dynamically by the bot backend
# Include peer configs from peers directory
PostUp = for f in /etc/amneziawg/peers/*.conf; do [ -f "\$f" ] && awg addconf awg0 "\$f"; done
EOF

chmod 600 "${CONFIG_DIR}/awg0.conf"

echo ""
echo "=== AmneziaWG Setup Complete ==="
echo "Server public key: $(cat "${CONFIG_DIR}/server_public.key")"
echo "Listen port: ${AWG_LISTEN_PORT}"
echo "Subnet: ${AWG_SUBNET}"
echo "Server IP: ${AWG_SERVER_IP}"
echo ""
echo "Next steps:"
echo "  1. Open firewall: ufw allow ${AWG_LISTEN_PORT}/udp"
echo "  2. Start: docker compose up -d"
echo "  3. Verify: docker exec amneziawg awg show"
