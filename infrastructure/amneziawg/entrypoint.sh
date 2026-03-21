#!/bin/sh
if [ ! -f /etc/amneziawg/awg0.conf ]; then
  echo 'ERROR: awg0.conf not found'
  exit 1
fi

amneziawg-go awg0 &
AWG_PID=$!
sleep 2

grep -v '^Address\|^PostUp\|^PostDown\|^DNS\|^SaveConfig\|^MTU' /etc/amneziawg/awg0.conf > /tmp/stripped.conf
awg setconf awg0 /tmp/stripped.conf

ADDR=$(grep '^Address' /etc/amneziawg/awg0.conf | cut -d= -f2 | tr -d ' ')
ip -4 address add $ADDR dev awg0 2>/dev/null || true
ip link set mtu 1420 up dev awg0

IFACE=$(ip route | awk '/default/ {print $5; exit}')
iptables -A FORWARD -i awg0 -j ACCEPT 2>/dev/null || true
iptables -t nat -A POSTROUTING -o ${IFACE:-eth0} -j MASQUERADE 2>/dev/null || true

# Load ALL peer configs
for f in /etc/amneziawg/peers/*.conf; do
  if [ -f "$f" ]; then
    awg addconf awg0 "$f" 2>/dev/null && echo "Loaded peer: $f"
  fi
done

echo "AmneziaWG ready ($(awg show awg0 | grep -c 'peer:') peers)"
awg show awg0

trap 'kill $AWG_PID 2>/dev/null; exit 0' SIGTERM SIGINT
# Keep container alive
while kill -0 $AWG_PID 2>/dev/null; do
  sleep 60
done
