# 003: Persist legal consents in backend

## Status
Accepted

## Date
2026-03-07

## Context

Mini App needed a first-run legal acceptance flow for:

- Privacy Policy
- Terms of Use
- Personal data processing consent
- Marketing consent

The acceptance must survive device changes, Telegram WebView resets and app reinstalls. It also needs a versioned re-consent path for future legal updates.

## Decision

Legal consents are stored on the `proxycraft_users` record in the backend, not in `localStorage` and not in Telegram client state.

The backend persists:

- `legal_consents_version`
- `privacy_policy_accepted_at`
- `terms_of_use_accepted_at`
- `personal_data_consent_accepted_at`
- `marketing_consent_granted`
- `marketing_consent_updated_at`

The current required version is controlled by the backend constant `LEGAL_CONSENTS_VERSION`.

The Mini App is gated by `/api/v1/me`. If required consents are missing or have an outdated version, the app shows a full-screen consent gate and blocks normal navigation until the user submits required consents.

## Consequences

### Positive

- Consent state is durable across devices and sessions.
- Future re-consent is trivial: bump `LEGAL_CONSENTS_VERSION`.
- Marketing opt-in is tracked separately from mandatory legal consents.
- Webapp stays stateless with respect to legal acceptance.

### Negative

- Adds a user-model migration and one more authenticated API endpoint.
- Existing users will be re-gated after rollout until they accept the current version.

## Alternatives considered

### Browser-only storage

Rejected because it is not durable and would diverge across devices and Telegram WebViews.

### Single boolean "accepted all"

Rejected because mandatory consents and optional marketing consent need separate auditability.
