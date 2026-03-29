# ProxyCraft

Complete, production-ready VPN & proxy service sold through a Telegram bot. Users buy subscriptions via the bot, get connection configs instantly, and manage everything from a Telegram Mini App.

Built on top of [3xui-shop](https://github.com/snoups/3xui-shop) v0.6.2, extended with MTProto proxy, WhatsApp proxy, payment integrations, admin panel, landing page, and production monitoring.

## What's Included

| Component | Stack | Description |
|-----------|-------|-------------|
| **Telegram Bot** | Python 3.12, aiogram 3 | Subscription sales, VPN/proxy management, payments, referral system |
| **REST API** | aiohttp | Backend for webapp and admin panel, Telegram Login auth |
| **Web App** | React 19, Vite, Tailwind CSS 4 | Telegram Mini App for users to manage subscriptions |
| **Admin Panel** | React 19, Vite, Tailwind CSS 4 | Dashboard, user management, server monitoring |
| **Landing Page** | Astro 5, React, Tailwind CSS 4 | Marketing website with i18n (RU/EN), legal pages |
| **MTProto Proxy** | Docker, [mtprotoproxy](https://github.com/alexbers/mtprotoproxy) | Telegram proxy with TLS masking, hot-reloaded by the bot |
| **WhatsApp Proxy** | Docker, HAProxy | WhatsApp proxy with per-user ports, atomic config reloads |
| **AmneziaWG** | Docker, amneziawg-go | Obfuscated WireGuard for anti-DPI bypass |

## Features

**VPN & Proxy Products**
- VLESS + Reality VPN via [3X-UI](https://github.com/MHSanaei/3x-ui) panel
- MTProto proxy for Telegram access
- WhatsApp proxy via HAProxy with per-user TLS ports
- AmneziaWG (obfuscated WireGuard) support
- Product bundles (Telegram+WhatsApp, VPN+all proxies)
- Flexible plans: 1/3/5 devices, 30/90/180/365 days

**Payments**
- Telegram Stars (built-in)
- YooKassa, YooMoney, T-Bank
- Cryptomus, Heleket (crypto)
- Abstract gateway interface for adding new providers

**Referral System**
- 2-level referrals: +30 days (L1), +3 days (L2)
- +7 days bonus for referred user on first payment
- Up to 365 days accumulated reward

**Operations**
- Production smoke tests with deterministic fixtures
- Post-deploy verification with Telegram alerts
- External geo-probes via Check-Host (SEA/EU/RU-friendly regions)
- GitHub Actions CI/CD for bot, webapp, landing
- Self-hosted runner for production deploys

**Internationalization**
- Bot: RU/EN via gettext (babel)
- Landing: RU/EN with automatic locale routing

## Architecture

```
                      Telegram Cloud
                           |
              +------------+------------+
              |                         |
         Telegram Bot              Mini App (webapp)
         (aiogram 3)             (React + Vite)
              |                         |
              +------------+------------+
                           |
                       REST API
                      (aiohttp)
                           |
              +-----+------+------+-----+
              |     |      |      |     |
           SQLite  Redis  3X-UI  MTProto WhatsApp
            (DB)   (FSM)  (VPN)  Proxy   Proxy
```

The bot manages proxy containers through shared Docker volumes -- it renders config files and triggers hot reloads without rebuilding images.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (for local development)
- Node.js 20+ (for webapp/admin/landing)
- A [3X-UI](https://github.com/MHSanaei/3x-ui) panel running on your VPN server
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Deploy

```bash
# 1. Clone and configure
git clone https://github.com/spyrae/proxycraft.git
cd proxycraft
cp .env.example .env
# Edit .env with your values (bot token, 3X-UI credentials, payment keys)
# Edit app/data/products.json with your pricing

# 2. Start the bot + proxies
docker compose up -d

# 3. Deploy landing page (Cloudflare Pages)
cd landing && npm install && npm run build
npx wrangler pages deploy dist --project-name=your-project

# 4. Deploy webapp (Cloudflare Pages)
cd webapp && npm install && npm run build
npx wrangler pages deploy dist --project-name=your-webapp
```

### Configuration

All settings are in `.env.example` with descriptions. Key sections:

| Section | Variables | Purpose |
|---------|-----------|---------|
| Bot | `BOT_TOKEN`, `BOT_ADMINS` | Telegram bot credentials |
| 3X-UI | `XUI_USERNAME`, `XUI_PASSWORD` | VPN panel access |
| Shop | `SHOP_CURRENCY`, `SHOP_TRIAL_*` | Pricing and trial settings |
| MTProto | `SHOP_MTPROTO_*` | Telegram proxy config |
| WhatsApp | `SHOP_WHATSAPP_*` | WhatsApp proxy config |
| Payments | `YOOKASSA_*`, `TBANK_*` | Payment gateway credentials |
| Smoke | `SMOKE_*` | Production testing config |

## Project Structure

```
proxycraft/
├── app/                    # Python bot + API
│   ├── bot/
│   │   ├── routers/        # 12 Telegram command handlers
│   │   ├── services/       # VPN, MTProto, WhatsApp, referral, etc.
│   │   ├── payment_gateways/ # 6 payment providers
│   │   ├── api/            # REST API (routes, middleware, auth)
│   │   ├── tasks/          # Scheduled jobs (expiry, auto-renew)
│   │   └── admin_tools/    # Admin commands via Telegram
│   ├── db/models/          # 15 SQLAlchemy models
│   ├── data/products.json  # Product catalog
│   └── locales/            # i18n translations (RU/EN)
├── webapp/                 # Telegram Mini App (React)
├── admin/                  # Admin panel (React)
├── landing/                # Marketing website (Astro)
├── mtproto/                # MTProto proxy Docker image
├── whatsapp/               # WhatsApp proxy Docker image
├── infrastructure/         # AmneziaWG, GitHub runners
├── scripts/                # Smoke tests, geo probes, migrations
├── docs/                   # Architecture Decision Records
├── docker-compose.yml      # Bot + Redis + MTProto + WhatsApp
└── .github/workflows/      # CI/CD (deploy, geo-probes)
```

## Production Monitoring

### Smoke Tests

```bash
# Provision test fixtures
docker exec proxycraft-bot poetry run python -m scripts.provision_smoke_fixtures --json

# Run smoke checks
docker exec proxycraft-bot poetry run python -m scripts.run_smoke_checks --json

# Full post-deploy verification with Telegram alerts
docker exec proxycraft-bot poetry run python -m scripts.run_post_deploy_verification --json --notify
```

### Geo Probes

External availability checks from 3 regions via Check-Host, running every 6 hours via GitHub Actions:

```bash
docker exec proxycraft-bot poetry run python -m scripts.run_geo_probes --json --notify
```

## Tech Stack

**Backend:** Python 3.12 / aiogram 3.15 / SQLAlchemy 2.0 (async) / Alembic / APScheduler / aiohttp / Redis

**Frontend:** React 19 / Vite / TypeScript / Tailwind CSS 4 / TanStack Query 5

**Landing:** Astro 5 / React / Tailwind CSS 4

**Infrastructure:** Docker Compose / Traefik / Cloudflare Pages / GitHub Actions

**VPN/Proxy:** 3X-UI (VLESS+Reality) / mtprotoproxy / HAProxy / AmneziaWG

## License

MIT -- see [LICENSE](LICENSE).

Originally forked from [3xui-shop](https://github.com/snoups/3xui-shop) by [snoups](https://github.com/snoups).
