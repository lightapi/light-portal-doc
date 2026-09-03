# Enterprise Portal BFF

`portal-bff-sso` exists only in the `portal-config-bootstrap` enterprise
overlay. It uses the `light-gateway` image but is a distinct runtime identity
from the base OAuth Portal BFF.

## Responsibilities

- Terminate the enterprise Portal TLS connection.
- Serve the SSO-enabled Portal View artifact.
- Validate Microsoft Entra tokens through `security-msal`.
- Exchange the external token for the platform token expected by downstream
  Portal services.
- Apply its own cookies, handlers, host routing and Config Server snapshot.

## Required private inputs

The overlay requires values such as `MSAL_TENANT_ID`, `MSAL_CLIENT_ID`,
`MSAL_EXCHANGE_CLIENT_ID`, `MSAL_EXCHANGE_CLIENT_SECRET`, and
`PORTAL_BFF_SSO_LIGHT_PORTAL_AUTHORIZATION`. Exact names and required checks are
defined in `.env.bootstrap.example` and `docker-compose.bootstrap.yml`.

Client secret, Portal token and TLS private key are secrets. Tenant ID, public
client ID, redirect URI and audience are identifiers but must still remain
consistent across Entra, the built SPA and Gateway configuration.

## Listener and cache

The listener defaults to host port `8445`. The service uses its own config-cache
volume so the base and SSO BFF snapshots cannot overwrite one another. A
snapshot for the base Gateway identity is not valid for this BFF.

Changing Entra SPA build-time values requires rebuilding Portal View. Changing
runtime secret/environment values requires recreating the container. Changing a
promoted Gateway module requires the supported snapshot/reload lifecycle.

