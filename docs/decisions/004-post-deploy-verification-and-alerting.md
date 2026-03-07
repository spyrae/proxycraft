# ADR 004: Post-Deploy Verification and Operational Alerting

## Status

Accepted

## Context

`RB-537` and `RB-538` introduced deterministic production smoke fixtures and a smoke-runner that validates `VPN`, `MTProto`, and `WhatsApp` through real service code paths after every deploy. That closed the gap between "container is running" and "core user path still works", but the operational story was still incomplete:

1. Production deploy relied on inline shell glue in GitHub Actions instead of a single verification entrypoint.
2. There was no explicit separation between deploy-blocking failures and warning-only degradation.
3. Team members did not receive an automatic Telegram alert when post-deploy verification detected a critical regression.
4. There was no dedicated HTTP health endpoint for the Mini App API itself.

For production-grade operations, deploy verification must be explicit, reproducible, severity-aware, and able to notify operators without manual log inspection.

## Decision

Introduce a dedicated orchestration command `scripts/run_post_deploy_verification.py` and make it the single post-deploy verification entrypoint in production.

The verification flow now performs:

1. `bot API health` via unauthenticated `GET /api/v1/health`
2. `VPN server pool availability` per sold location after `sync_servers(force_refresh=True)`
3. smoke fixture provisioning via `scripts.provision_smoke_fixtures`
4. runtime endpoint checks for `MTProto` and `WhatsApp`
5. full smoke validation via `scripts.run_smoke_checks`

The script classifies outcomes into two severities:

- `deploy-blocking`
- `warning-only`

Only `deploy-blocking` failures fail the deploy job. `warning-only` results do not fail the workflow, but they remain visible in logs and can trigger notifications.

If verification finds a blocking failure, or warnings when `--notify-warnings` is enabled, the script sends a Telegram alert to `BOT_ADMINS` through the existing `NotificationService`.

The production deploy workflow no longer orchestrates smoke provision/checks via ad-hoc shell functions. Instead it invokes:

```bash
poetry run python /app/scripts/run_post_deploy_verification.py --json --notify --notify-warnings
```

## Consequences

### Positive

- Production deploy now has one canonical operational verification entrypoint.
- The Mini App API has a real HTTP health endpoint instead of implicit container liveness.
- Deploy logs show whether an issue is blocking or warning-only.
- Operators receive Telegram alerts without having to inspect GitHub logs manually.
- The workflow enforces a clearer distinction between CI/build success and real production health.

### Trade-offs

- Post-deploy verification becomes more opinionated and stricter.
- Server-pool checks add extra login/refresh pressure on 3X-UI during deploy.
- Warning notifications can create noise if degradation is persistent and unresolved.

## Implementation Notes

- Health endpoint: `app/bot/api/routes.py`, `app/bot/api/middleware.py`
- Orchestrator: `scripts/run_post_deploy_verification.py`
- Existing smoke suite reused from:
  - `scripts/provision_smoke_fixtures.py`
  - `scripts/run_smoke_checks.py`
- Deploy integration: `.github/workflows/deploy.yml`
