# ADR 002: Production Smoke Runner Inside Bot Runtime

## Status

Accepted

## Context

ProxyCraft production deploys can succeed while one of the user-facing products is already broken at runtime:

- MTProto can expose an invalid link or dead port
- WhatsApp proxy can publish a dead frontend port
- VPN can return a broken subscription URL or lose the client inside 3X-UI

Simple container healthchecks are not enough because they do not exercise the real product code paths that generate links and endpoints for end users.

## Decision

Introduce a dedicated production smoke-runner executed inside the `bot` container after deploy.

The runner must:

1. use real service methods from the production codebase
2. discover or pin a real subscription fixture from the production database
3. validate the generated link / connection info for each product
4. probe the corresponding network endpoint
5. fail the deploy if any critical product path is broken

The runner is implemented as `/app/scripts/run_smoke_checks.py` and is executed through:

```bash
docker compose exec -T bot poetry run python /app/scripts/run_smoke_checks.py --json
```

## Consequences

### Positive

- Deployment success now means user-critical paths were actually exercised
- Smoke checks use the same runtime, env vars and dependencies as the production bot
- The system can later be upgraded to stable smoke fixtures without changing the execution model

### Trade-offs

- Deploy becomes stricter and can fail on real data/runtime problems
- Until dedicated fixtures are introduced, auto-discovery depends on viable live subscriptions in production

## Follow-up

- RB-538: introduce permanent smoke fixtures for all products
- RB-539: add external geo-probes for location-sensitive validation
