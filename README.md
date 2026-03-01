# VPNCraft

Telegram bot for selling VPN & proxy subscriptions. Built on top of [3xui-shop](https://github.com/snoups/3xui-shop) v0.6.2.

## Stack

- Python 3.12, aiogram 3
- 3X-UI panel (VLESS+WebSocket+CDN)
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
```

## License

MIT (inherited from 3xui-shop)
