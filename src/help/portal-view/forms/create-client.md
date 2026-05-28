# Create Client

Use this form to create an OAuth client.

An OAuth client can be associated with an app, API version, or instance,
depending on the selected ownership context.

Important fields:

- `clientName`: user-facing client name
- `clientType`: client type
- `clientProfile`: OAuth profile
- `providerId`: OAuth provider
- `ownerPositionId`: optional position owner for team access

## Save The Generated Secret

After the client is created, the portal returns the generated `clientId` and
`clientSecret`. Copy both values and store them in your secret manager before
leaving the result page.

The portal does not persist the clear `clientSecret`. It stores only a verifier
for future authentication, so the original secret cannot be shown again. If the
secret is lost, regenerate it from the OAuth Client page and update any systems
that use the old secret.

## Save The Generated Credentials

After the client is created, the response includes the generated `clientId` and
`clientSecret`. Copy both values and store them in the target application's
secret manager or deployment configuration immediately.

The clear `clientSecret` is shown only once. The portal stores only a verifier
for later authentication, so it cannot show the original secret again after you
leave the result page.

If the secret is lost, use the OAuth Client page to regenerate it. Regeneration
creates a new secret and invalidates the old secret for future token requests.
