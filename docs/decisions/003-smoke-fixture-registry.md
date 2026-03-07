# ADR 003: Production Smoke Fixture Registry

## Status

Accepted

## Context

`RB-537` introduced a production smoke-runner that validates `VPN`, `MTProto`, and `WhatsApp` through real service code paths after every deploy. The first version relied on the latest active subscription rows in the production database, which created three problems:

1. Smoke checks could validate случайную боевую подписку вместо контролируемого fixture.
2. Deploy verification became nondeterministic when there were no active rows for a product.
3. Recovering after a failed deploy required manual data preparation.

For production-grade verification, smoke checks need dedicated users and reproducible subscriptions that survive clean rebuilds and can be reprovisioned idempotently.

## Decision

Introduce a dedicated registry table `proxycraft_smoke_fixtures` and a provisioning command `scripts.provision_smoke_fixtures`.

The provisioning flow:

1. Creates or refreshes dedicated smoke users with deterministic Telegram IDs.
2. Ensures one stable fixture per key:
   - `vpn_amsterdam`
   - `vpn_saint_petersburg`
   - `mtproto`
   - `whatsapp`
3. Persists the resolved subscription IDs in `proxycraft_smoke_fixtures`.
4. Runs idempotently before every production smoke check.

The smoke-runner now resolves fixtures from the registry instead of scanning arbitrary live rows. Explicit `SMOKE_*_SUBSCRIPTION_ID` env overrides remain available only as an escape hatch.

## Consequences

### Positive

- Production deploy verification is deterministic.
- Fixtures are reproducible after failed deploys and fresh environment rebuilds.
- Smoke checks no longer depend on random customer subscriptions.
- VPN verification now covers both production locations via separate fixtures.

### Trade-offs

- Adds one extra provisioning step to deploy.
- Introduces a small amount of permanent test data in production.
- Requires keeping fixture users out of customer-facing analytics and billing flows.

## Implementation Notes

- Registry model: `app/db/models/smoke_fixture.py`
- Migration: `012_smoke_fixture_registry`
- Provisioner: `scripts/provision_smoke_fixtures.py`
- Smoke runner: `scripts/run_smoke_checks.py`
- Deploy integration: `.github/workflows/deploy.yml`
