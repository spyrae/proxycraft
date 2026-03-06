# VPNCraft

Telegram bot for selling VPN & proxy subscriptions. Built on top of [3xui-shop](https://github.com/snoups/3xui-shop) v0.6.2.

## Stack

- Python 3.12, aiogram 3
- 3X-UI panel (VLESS+WebSocket+CDN)
- MTProto proxy packaged as a dedicated Docker image with runtime config synced from DB + env
- WhatsApp proxy packaged as a dedicated Docker image with runtime TLS bootstrap + HAProxy reloads
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
```

## License

MIT (inherited from 3xui-shop)
