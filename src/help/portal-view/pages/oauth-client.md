# OAuth Client

Use OAuth Client to create and manage OAuth clients for applications, APIs, or
instances.

This page is owner-aware. Regular users should see only OAuth clients they own
or can access through their position. OAuth client administrators can see all
OAuth clients for the host.

Common actions:

- create an OAuth client
- update client metadata
- regenerate a client secret
- review scopes and token-exchange settings
- open client tokens

## Client Secrets

When a client is created, the page returns the generated `clientId` and
`clientSecret`. Copy and store the secret immediately. The portal stores only a
password verifier for future authentication; it cannot show the original clear
secret again.

If the secret is lost, use the Regenerate Client Secret row action. The action
creates a new secret, replaces the stored verifier, and shows the new clear
secret one time. Copy it before closing the dialog.

Regenerating a secret affects future client authentication. Existing access
tokens remain valid until they expire, but new token requests must use the new
secret after the event is processed.
