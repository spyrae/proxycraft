#!/bin/sh
if [ ! -f /etc/amneziawg/awg0.conf ]; then
  echo 'ERROR: awg0.conf not found'
  exit 1
fi

# Setup script: configure interface, then keep container alive
# amneziawg-go runs as a daemon, awg-quick manages it
awg-quick up /etc/amneziawg/awg0.conf 2>&1 || {
  echo "awg-quick up failed, exiting"
  exit 1
}

# Load peer configs
for f in /etc/amneziawg/peers/*.conf; do
  if [ -f "$f" ]; then
    awg addconf awg0 "$f" 2>/dev/null && echo "Loaded peer: $f"
  fi
done

echo "AmneziaWG ready"
awg show awg0

# Keep container running
trap 'awg-quick down /etc/amneziawg/awg0.conf 2>/dev/null; exit 0' SIGTERM SIGINT
while true; do
  sleep 3600 &
  wait $!
done
