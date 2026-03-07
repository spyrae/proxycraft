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
docker exec -e PYTHONPATH=/app proxycraft-bot poetry run python -m scripts.provision_smoke_fixtures --json
docker exec -e PYTHONPATH=/app proxycraft-bot poetry run python -m scripts.run_smoke_checks --json
docker exec -e PYTHONPATH=/app proxycraft-bot poetry run python -m scripts.run_smoke_checks --json --product vpn
docker exec -e PYTHONPATH=/app proxycraft-bot poetry run python -m scripts.run_post_deploy_verification --json --notify --notify-warnings
```

If a product uses an internal-only probe host in production, pass the same `SMOKE_*` env overrides to `docker exec` that the deploy workflow uses.

The fixture provisioner:
- creates dedicated smoke users with deterministic Telegram IDs
- maintains one stable smoke subscription per product fixture (`vpn_amsterdam`, `vpn_saint_petersburg`, `mtproto`, `whatsapp`)
- stores fixture metadata in `proxycraft_smoke_fixtures`
- can safely be rerun after a failed deploy or a clean environment rebuild

The smoke-runner:
- can execute a single product check via `--product mtproto|whatsapp|vpn` or all checks sequentially
- uses real service methods for MTProto / WhatsApp / VPN link generation
- resolves stable fixtures from the `proxycraft_smoke_fixtures` registry instead of random live rows
- supports explicit fixture overrides via optional `SMOKE_*_SUBSCRIPTION_ID` env vars
- supports optional internal probe overrides (`SMOKE_*_PROBE_HOST`, `SMOKE_VPN_*_PROBE_URL`) for same-host Docker deployments
- fails deploy if a critical product path is broken

The post-deploy verification runner:
- checks `GET /api/v1/health` before deeper verification starts
- validates VPN server-pool availability per sold location with `deploy-blocking` vs `warning-only` severity
- provisions smoke fixtures and runs the full smoke suite in one command
- sends Telegram alerts to `BOT_ADMINS` for critical failures and optional warnings
- is the single verification entrypoint used by the production deploy workflow

## External Geo Probes

Manual run:

```bash
docker exec -e PYTHONPATH=/app proxycraft-bot poetry run python -m scripts.run_geo_probes --json --trigger manual
docker exec -e PYTHONPATH=/app proxycraft-bot poetry run python -m scripts.run_geo_probes --json --product vpn --notify --notify-warnings
```

The geo-probe runner:
- provisions smoke fixtures before probing public endpoints
- resolves real public targets for `MTProto`, `WhatsApp`, `VPN Amsterdam`, and `VPN Saint Petersburg`
- runs external checks through Check-Host from three regions: `SEA`, `EU`, and `RU-friendly`
- persists run metadata in `proxycraft_geo_probe_runs`
- persists per-region observations in `proxycraft_geo_probe_results`
- sends Telegram alerts to `BOT_ADMINS` when failures or warning-only degradation are detected

The scheduled workflow:
- lives in `.github/workflows/geo-probes.yml`
- runs every 6 hours and is also available through `workflow_dispatch`
- executes inside the production `proxycraft-bot` container via SSH, so it uses the same code and fixture registry as the live stack

Optional env overrides:
- `GEO_PROBE_PREFERRED_NODES_SEA`
- `GEO_PROBE_PREFERRED_NODES_EU`
- `GEO_PROBE_PREFERRED_NODES_RU_FRIENDLY`
- `GEO_PROBE_HTTP_TIMEOUT`
- `GEO_PROBE_POLL_ATTEMPTS`
- `GEO_PROBE_POLL_INTERVAL`
- `GEO_PROBE_FIXTURE_TIMEOUT`

## License

MIT (inherited from 3xui-shop)
