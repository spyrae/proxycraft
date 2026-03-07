# VPNCraft

Telegram bot for selling VPN & proxy subscriptions. Built on top of [3xui-shop](https://github.com/snoups/3xui-shop) v0.6.2.

## Stack

- Python 3.12, aiogram 3
- 3X-UI panel (VLESS+WebSocket+CDN)
- MTProto proxy packaged as a dedicated Docker image with runtime config synced from DB + env
- WhatsApp proxy packaged as a dedicated Docker image with runtime TLS bootstrap + HAProxy reloads
- Production smoke-runner for VPN / MTProto / WhatsApp executed inside the bot container
- SQLite (→ PostgreSQL later)
- Redis (FSM storage)
- Traefik (reverse proxy, SSL)
- Docker Compose

## Quick Start

```bash
cp .env.example .env
# edit .env with your values
# edit app/data/products.json with your pricing

docker compose up -d
```

## Architecture

```
Cloudflare CDN → nginx :443 → Xray (VLESS+WS)
Telegram → Traefik → Bot :8080
Bot → 3X-UI API (manage VPN clients)
Bot → MTProto runtime config (render + hot reload)
Bot → HAProxy config for WhatsApp proxy (atomic write + validated reload)
Bot → production smoke checks (real subscription generation + endpoint probes)
```

## Production Smoke Checks

Manual run:

```bash
docker compose exec -T bot poetry run python /app/scripts/run_smoke_checks.py --json
```

The smoke-runner:
- uses real service methods for MTProto / WhatsApp / VPN link generation
- auto-discovers a viable subscription fixture from the production database
- supports pinned fixtures via optional `SMOKE_*_SUBSCRIPTION_ID` env vars
- fails deploy if a critical product path is broken

## License

MIT (inherited from 3xui-shop)
