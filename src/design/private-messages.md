# Private Messages

## Problem

Portal users need a way to exchange private messages from the user profile
without exposing email addresses to each other. The sender should only need a
recipient user id or a display-safe user label. The backend can resolve email
internally when it needs to send an external notification, but email must not be
part of the user-facing message contract.

## Current State

The current codebase already has a partial private-message skeleton:

- `user-command` exposes `lightapi.net/user/sendMessage/0.1.0`.
- The `sendMessage` request contains `userId`, `subject`, and `content`.
- `light-portal` defines `PrivateMessageSentEvent`.
- `portal-db` defines `message_t`.
- `portal-view` has a mail menu, a private messages page, and a
  `privateMessage` form.
- `user-query` exposes `lightapi.net/user/getPrivateMessage/0.1.0`.

The current implementation is not complete enough to support production use:

- `GetPrivateMessage` has its real implementation commented out and currently
  returns `null`.
- `SendMessage` resolves the recipient through `queryUserById`, then stores the
  whole response as `toEmail`. That lookup currently returns too much user data,
  including email and sensitive fields that should not be exposed through a
  peer messaging flow.
- `SendMessage` does not put `fromId` into event data, but the projection code
  reads `fromId` from event data.
- The `message_t` table now has `host_id NOT NULL`, but the projection insert
  does not write `host_id`.
- The table is inbox-style storage, keyed by sender and nonce, and does not
  model conversations, read state, participant visibility, or per-user delete.
- The UI mostly relies on the mail menu response and navigation state. The
  messages page should load its own data from the query API.
- The existing private-message tests are disabled stubs.

## Goals

- Let one logged-in user send a message to another portal user without knowing
  or seeing the recipient email.
- Keep the message model host-scoped so tenant boundaries are explicit.
- Derive sender identity from the authorization token, not from form input.
- Store user ids in message records and events. Do not store recipient email in
  the message projection unless a short migration bridge requires it.
- Support an inbox page, unread badge, conversation view, reply, read state, and
  per-user hide/delete.
- Keep email notification as an optional side effect that resolves the
  recipient email internally.
- Provide a path from the existing `message_t` skeleton to a conversation-based
  model without breaking existing UI routes immediately.

## Non-Goals

- Do not build group chat in the first phase.
- Do not expose email addresses in message APIs, events, UI state, or task
  context.
- Do not use private messages as an audit or support-ticket system.
- Do not implement WebSocket or SSE push in the first phase. Polling is enough
  until the read/write model is stable.
- Do not make public user lookup broader as part of this feature.

## Privacy Rules

Private messages should be user-id based at every external boundary.

The UI may show:

- Display name.
- Avatar or initials.
- User id when no better label exists.
- Message subject, preview, content, and timestamps.

The UI must not show:

- Sender email.
- Recipient email.
- Password, token, nonce, or other profile internals from `user_t`.

The backend may resolve recipient email only inside trusted server code for
external email notification. That internal lookup should return the minimum
fields required, ideally `user_id`, `email`, current host membership, and a
display label.

## Recommended Data Model

For a chat-like experience, introduce conversation identity instead of treating
each message as an isolated inbox row.

```sql
CREATE TABLE private_conversation_t (
    host_id              UUID NOT NULL,
    conversation_id      UUID NOT NULL,
    participant_low_id   UUID NOT NULL,
    participant_high_id  UUID NOT NULL,
    created_ts           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_message_id      UUID NULL,
    last_message_ts      TIMESTAMP WITH TIME ZONE NULL,
    PRIMARY KEY (host_id, conversation_id),
    UNIQUE (host_id, participant_low_id, participant_high_id),
    FOREIGN KEY (host_id) REFERENCES host_t(host_id) ON DELETE CASCADE
);
```

`participant_low_id` and `participant_high_id` are the two sorted user ids. This
gives each pair of users one stable conversation per host without relying on
email.

```sql
CREATE TABLE private_message_t (
    host_id          UUID NOT NULL,
    message_id       UUID NOT NULL,
    conversation_id  UUID NOT NULL,
    from_user_id     UUID NOT NULL,
    to_user_id       UUID NOT NULL,
    subject          VARCHAR(256) NULL,
    content          TEXT NOT NULL,
    send_ts          TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (host_id, message_id),
    FOREIGN KEY (host_id, conversation_id)
        REFERENCES private_conversation_t(host_id, conversation_id)
        ON DELETE CASCADE
);
```

```sql
CREATE TABLE private_message_state_t (
    host_id      UUID NOT NULL,
    message_id   UUID NOT NULL,
    user_id      UUID NOT NULL,
    read_ts      TIMESTAMP WITH TIME ZONE NULL,
    deleted_ts   TIMESTAMP WITH TIME ZONE NULL,
    PRIMARY KEY (host_id, message_id, user_id),
    FOREIGN KEY (host_id, message_id)
        REFERENCES private_message_t(host_id, message_id)
        ON DELETE CASCADE
);
```

The state table keeps read and delete behavior per participant. A user deleting
a message should hide it from that user only. It should not erase the other
participant's copy.

Recommended indexes:

```sql
CREATE INDEX idx_private_conversation_last_message
    ON private_conversation_t (host_id, participant_low_id, participant_high_id, last_message_ts DESC);

CREATE INDEX idx_private_message_conversation_ts
    ON private_message_t (host_id, conversation_id, send_ts DESC);

CREATE INDEX idx_private_message_to_user_ts
    ON private_message_t (host_id, to_user_id, send_ts DESC);

CREATE INDEX idx_private_message_state_unread
    ON private_message_state_t (host_id, user_id)
    WHERE read_ts IS NULL AND deleted_ts IS NULL;
```

If the first implementation needs to reuse `message_t`, treat it as a migration
bridge only. Add `from_user_id`, `to_user_id`, `message_id`, `read_ts`, and
per-user delete columns, then migrate to the conversation tables once the API
contract is stable.

## Event Model

Keep the event-driven command/query pattern. A message send should create a
CloudEvent and the query-side projection should update the private-message
tables.

Recommended event data:

```json
{
  "hostId": "019...",
  "conversationId": "019...",
  "messageId": "019...",
  "fromUserId": "019...",
  "toUserId": "019...",
  "subject": "Question about the API",
  "content": "Can you take a look at this?"
}
```

`fromUserId` and `hostId` are derived from the token. `toUserId`, `subject`, and
`content` come from validated request data. `conversationId` can be generated by
the command side after looking up or creating the pair conversation, or it can
be derived during projection from the participant pair.

Do not put `toEmail` into `PrivateMessageSentEvent`. Email notification should
be a separate trusted server-side action.

## API Contracts

### Send Message

Keep the existing `sendMessage` action name for compatibility, but change the
contract to be user-id based.

```json
{
  "toUserId": "019...",
  "conversationId": "019...",
  "subject": "Question about the API",
  "content": "Can you take a look at this?"
}
```

`conversationId` is optional. If absent, the backend resolves or creates the
conversation for the current user and `toUserId`.

Server responsibilities:

- Require an authorization-code token.
- Derive `fromUserId` from the token.
- Derive `hostId` from the active user host.
- Validate that `toUserId` belongs to the same host.
- Reject empty content and enforce size limits.
- Optionally reject self-messages unless a product decision allows notes to
  self.
- Write the event through the existing command event-store path.
- Send optional external email notification after the command is accepted.

### Conversation List

Add or evolve a query endpoint for the inbox list.

```json
{
  "offset": 0,
  "limit": 25
}
```

The backend derives `hostId` and `userId` from the token. The response should
include only conversations involving the current user.

```json
{
  "total": 1,
  "conversations": [
    {
      "conversationId": "019...",
      "otherUserId": "019...",
      "otherUserLabel": "Jane Smith",
      "lastMessageTs": "2026-05-08T13:30:00Z",
      "lastMessagePreview": "Can you take a look at this?",
      "unreadCount": 2
    }
  ]
}
```

### Conversation Messages

```json
{
  "conversationId": "019...",
  "offset": 0,
  "limit": 50
}
```

The backend validates that the current user is one of the participants.

```json
{
  "conversationId": "019...",
  "messages": [
    {
      "messageId": "019...",
      "fromUserId": "019...",
      "fromUserLabel": "Jane Smith",
      "subject": "Question about the API",
      "content": "Can you take a look at this?",
      "sendTs": "2026-05-08T13:30:00Z",
      "read": false
    }
  ]
}
```

### Unread Count

The mail badge should call a count endpoint instead of loading all messages.

```json
{
  "count": 3
}
```

### Mark Read and Delete

`markPrivateConversationRead` should mark unread rows in
`private_message_state_t` for the current user and conversation.

`deletePrivateMessage` or `hidePrivateConversation` should set `deleted_ts` for
the current user only.

## Operational Cleanup

Private messages are user content, not operational status rows. They should not
be hard-deleted only because they are old while either participant can still see
them.

The operational cleanup job may purge active private-message rows only when all
participant state rows for the message have `deleted_ts` set and the latest
`deleted_ts` is older than `privateMessageRetentionDays`.

Cleanup responsibilities:

- Select purge candidates from `private_message_t` joined to
  `private_message_state_t`.
- Require every participant state row for the message to have `deleted_ts` set.
- Use `MAX(deleted_ts)` as the retention clock so the grace period starts after
  the last participant deletes the message.
- Delete `private_message_state_t` rows first, then delete the
  `private_message_t` row in the same transaction.
- Leave `private_conversation_t` rows in place so the participant pair keeps a
  stable conversation identity if a new message is sent later.
- Skip private-message cleanup when `privateMessageRetentionDays` is less than
  or equal to zero.

The cleanup job should not purge visible messages, partially deleted messages,
or recently deleted-by-all messages. A separate maximum retention policy for
undeleted private messages would need an explicit product/security decision.

## Authorization

The command and query handlers must not trust user ids supplied by the client
for the current user. The current user is always the token subject.

Rules:

- A sender can send only as themself.
- A user can read only conversations where they are a participant.
- A user can mark read or delete only their own state rows.
- Admin visibility should be a separate explicit support/admin endpoint if it
  is needed later.
- Cross-host messaging should be rejected in the first phase. If cross-host
  messaging is later needed, the contract must model the recipient host
  explicitly and pass a product/security review.

## Portal View

Use the current profile surfaces but make them data-driven:

- `MailMenu` should poll unread count and show a small list of recent
  conversations only after the menu opens.
- `/app/messages` should fetch conversation data directly. It should not depend
  on `location.state` from `MailMenu`.
- The `privateMessage` form should use `toUserId`, not `userId`, to avoid
  confusing recipient identity with the current user.
- Reply should prefill `toUserId` and optionally `conversationId`.
- User-facing labels should come from a display-safe user label endpoint.
- Empty inbox, loading, and error states should be explicit.

The first UI can be an inbox plus conversation thread. Real-time typing,
presence, attachments, and rich-text editing are later enhancements.

## Migration Plan

### Phase 0: Stop the Broken Behavior

- Make `GetPrivateMessage` return valid JSON even before the new model is
  complete.
- Fix the existing projection insert to include `host_id` if `message_t` remains
  in use.
- Ensure `SendMessage` stores sender identity from the token.
- Stop using broad `queryUserById` output as a recipient email value.

### Phase 1: User-ID Based Backend

- Add the conversation/message/state tables.
- Update `PrivateMessageSentEvent` to use `fromUserId` and `toUserId`.
- Add a trusted recipient resolver that returns only internal fields needed for
  validation and optional email notification.
- Implement conversation list, conversation messages, unread count, mark-read,
  and hide/delete APIs.

### Phase 2: Portal View

- Update the mail badge to use unread count.
- Update `/app/messages` to load data directly.
- Update the `privateMessage` form and reply paths to use `toUserId`.
- Remove email assumptions from task context and UI state.

### Phase 3: Cleanup

- Remove `to_email` from the active private-message path.
- Remove disabled private-message tests and replace them with focused coverage.
- Ensure operational cleanup targets the active private-message tables and
  purges only messages deleted by all participants after the retention window.
- Add optional push delivery later if polling becomes insufficient.

## Testing

Backend tests should cover:

- Sender is derived from token and cannot be spoofed.
- Recipient must belong to the current host.
- Message event contains user ids, not emails.
- Projection writes host-scoped conversation and message rows.
- Inbox query returns only conversations for the current user.
- Conversation query rejects non-participants.
- Unread count increments for the recipient and clears after mark-read.
- Delete/hide affects only the current user's state.
- Operational cleanup purges only messages deleted by all participants after
  retention and keeps visible, partially deleted, and recently deleted messages.

Frontend tests should cover:

- Mail menu shows unread count without loading full inbox.
- Messages page fetches its own data.
- Reply pre-populates recipient context without email.
- Empty and error states do not produce JSON parse failures.

## Open Questions

- Should users be able to send messages to themselves as private notes?
- Should profile pages expose a "Message" action only for users in the same
  host, or should some cross-host flows be allowed?
- Should email notification include the sender display label, or only say that a
  portal message was received?
- Should any maximum retention policy apply to undeleted private messages?
- Should administrators have a separate support/audit view, and under what
  permission?
