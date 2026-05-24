# User Session

Use User Session to review and revoke OAuth sessions for your own account.

The User Session pages are self-service pages. They use the signed-in user's
identity from the authenticated session, and the backend self-service actions
apply the current user scope again. Browser table filters are only usability
controls; they are not the authorization boundary.

Available views:

- **My Sessions** shows active login sessions by default. Change the status
  filter if you need to review older revoked or expired sessions.
- **My Refresh Tokens** shows active refresh-token-backed sessions for your
  account.
- **My Session Audit** shows login, refresh, failure, and revocation events for
  your account.

Common actions:

- open audit history for a session
- open refresh tokens for a session
- revoke one of your sessions
- revoke a refresh-token-backed session

Revoking your current browser session signs you out after the revoke succeeds.
If the portal cannot identify whether the selected session is the current
browser session, it still warns that the action may sign you out.

Administrators should continue to use OAuth Admin for host-wide session,
refresh-token, and audit review.
